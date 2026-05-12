#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import duckdb
import pandas as pd


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
SKILLS_ROOT = os.path.abspath(os.path.join(SKILL_ROOT, ".."))
PROJECT_DIR = os.environ.get("STOCKMASTER_ROOT", os.path.abspath(os.path.join(SKILLS_ROOT, "..", "StockMaster")))
ROOT_DIR = os.path.join(PROJECT_DIR, "StockMaster")
DATACENTER_DIR = os.environ.get("STOCKMASTER_DATA_CENTER", os.path.join(PROJECT_DIR, "DataCenter"))
DEFAULT_SQLITE_PATH = os.path.join(DATACENTER_DIR, "market.sqlite")
DEFAULT_DUCKDB_PATH = os.path.join(DATACENTER_DIR, "market.duckdb")
DEFAULT_STRATEGY_DIR = os.path.join(DATACENTER_DIR, "Strategies")

WINDOWS = [5, 10, 20, 30, 60, 120, 233]


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_sqlite_table(sqlite_path: str, sql: str, params: Tuple[Any, ...] = ()) -> pd.DataFrame:
    with sqlite3.connect(sqlite_path) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def load_strategy(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def load_stock_names_from_json() -> Dict[str, str]:
    names: Dict[str, str] = {}
    stock_data_dir = os.path.join(DATACENTER_DIR, "StockData")
    if not os.path.exists(stock_data_dir):
        return names
    for dirpath, _, filenames in os.walk(stock_data_dir):
        for filename in filenames:
            if not filename.endswith(".json"):
                continue
            path = os.path.join(dirpath, filename)
            code = filename[:6]
            try:
                with open(path, "r", encoding="utf-8") as file:
                    obj = json.load(file)
                info = obj.get("info") or {}
                name = info.get("name")
                if name:
                    names[str(info.get("code") or code).zfill(6)] = str(name)
            except Exception:
                stem = os.path.splitext(filename)[0]
                if len(stem) > 6:
                    names[code] = stem[6:]
    return names


def is_missing_stock_name(value: Any, code: Any = None) -> bool:
    if value is None or pd.isna(value):
        return True
    text = str(value).strip()
    if not text:
        return True
    return code is not None and text == str(code).strip()


def init_duckdb_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS minute_bars (
        code VARCHAR,
        datetime TIMESTAMP,
        period VARCHAR,
        open DOUBLE,
        close DOUBLE,
        high DOUBLE,
        low DOUBLE,
        volume DOUBLE,
        amount DOUBLE,
        PRIMARY KEY (code, datetime, period)
    );
    """)


def sync_source_tables(conn: duckdb.DuckDBPyConnection, sqlite_path: str, limit_codes: int = 0) -> Tuple[int, int]:
    stocks = load_sqlite_table(sqlite_path, """
        SELECT code, name, market, market_id, board, is_st, industry, area, listed_at, status, updated_at
        FROM stocks
        ORDER BY code
    """)
    if limit_codes > 0:
        stocks = stocks.head(limit_codes)
        codes = tuple(stocks["code"].tolist())
        placeholders = ",".join(["?"] * len(codes))
        bars = load_sqlite_table(sqlite_path, f"""
            SELECT code, date, open, close, high, low, volume, amount, amplitude,
                   change_percent, change_amount, turnover_rate
            FROM daily_bars
            WHERE code IN ({placeholders})
            ORDER BY code, date
        """, codes)
    else:
        bars = load_sqlite_table(sqlite_path, """
            SELECT code, date, open, close, high, low, volume, amount, amplitude,
                   change_percent, change_amount, turnover_rate
            FROM daily_bars
            ORDER BY code, date
        """)

    if not stocks.empty:
        stocks["code"] = stocks["code"].astype(str).str.zfill(6)
        names = load_stock_names_from_json()
        if names:
            stocks["name"] = stocks.apply(
                lambda row: names.get(row["code"], row.get("name"))
                if is_missing_stock_name(row.get("name"), row["code"])
                else row.get("name"),
                axis=1
            )
    if not bars.empty:
        bars["code"] = bars["code"].astype(str).str.zfill(6)
        bars["date"] = bars["date"].astype(str)

    conn.register("stocks_df", stocks)
    conn.register("daily_bars_df", bars)
    conn.execute("""
    CREATE OR REPLACE TABLE stocks AS
    SELECT
        CAST(code AS VARCHAR) AS code,
        name,
        market,
        market_id,
        board,
        is_st,
        industry,
        area,
        listed_at,
        status,
        updated_at
    FROM stocks_df;
    """)
    conn.execute("""
    CREATE OR REPLACE TABLE daily_bars AS
    SELECT
        CAST(code AS VARCHAR) AS code,
        CAST(date AS VARCHAR) AS date,
        open,
        close,
        high,
        low,
        volume,
        amount,
        amplitude,
        change_percent,
        change_amount,
        turnover_rate
    FROM daily_bars_df;
    """)
    conn.unregister("stocks_df")
    conn.unregister("daily_bars_df")
    return len(stocks), len(bars)


def build_daily_features(conn: duckdb.DuckDBPyConnection) -> int:
    lag_columns = []
    return_columns = []
    ma_columns = []
    for window in WINDOWS:
        lag_columns.append(
            f"LAG(d.close, {window}) OVER (PARTITION BY d.code ORDER BY d.date) AS close_{window}d_ago"
        )
        return_columns.append(
            f"CASE WHEN close_{window}d_ago > 0 THEN (close - close_{window}d_ago) / close_{window}d_ago * 100 END AS return_{window}d"
        )
        ma_columns.append(
            f"AVG(d.close) OVER (PARTITION BY d.code ORDER BY d.date ROWS BETWEEN {window - 1} PRECEDING AND CURRENT ROW) AS ma{window}"
        )

    conn.execute(f"""
    CREATE OR REPLACE TABLE daily_features AS
    WITH base AS (
        SELECT
            d.code,
            d.date,
            d.close,
            d.volume,
            d.amount,
            d.change_percent,
            s.name,
            s.market,
            s.board,
            COALESCE(s.is_st, 0) AS is_st,
            s.industry,
            CASE
                WHEN COALESCE(s.is_st, 0) = 1 THEN 5.0
                WHEN COALESCE(CAST(s.board AS VARCHAR), '') LIKE '%创业%' OR d.code LIKE '30%' THEN 20.0
                WHEN COALESCE(CAST(s.board AS VARCHAR), '') LIKE '%科创%' OR d.code LIKE '688%' THEN 20.0
                WHEN COALESCE(CAST(s.board AS VARCHAR), '') LIKE '%北交%' OR COALESCE(CAST(s.market AS VARCHAR), '') = 'BSE'
                     OR d.code LIKE '8%' OR d.code LIKE '4%' THEN 30.0
                ELSE 10.0
            END AS limit_threshold,
            {", ".join(lag_columns)},
            {", ".join(ma_columns)},
            AVG(d.volume) OVER (PARTITION BY d.code ORDER BY d.date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS volume_ma5,
            AVG(d.volume) OVER (PARTITION BY d.code ORDER BY d.date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS volume_ma20,
            AVG(d.amount) OVER (PARTITION BY d.code ORDER BY d.date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS amount_ma5,
            AVG(d.amount) OVER (PARTITION BY d.code ORDER BY d.date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS amount_ma20
        FROM daily_bars d
        LEFT JOIN stocks s ON s.code = d.code
    ),
    scored AS (
        SELECT
            *,
            {", ".join(return_columns)},
            CASE WHEN ma20 IS NOT NULL AND close >= ma20 THEN TRUE ELSE FALSE END AS close_above_ma20,
            CASE WHEN ma60 IS NOT NULL AND close >= ma60 THEN TRUE ELSE FALSE END AS close_above_ma60,
            CASE WHEN volume_ma20 > 0 THEN volume / volume_ma20 END AS volume_ratio_20d,
            SUM(CASE WHEN change_percent + 0.15 >= limit_threshold THEN 1 ELSE 0 END)
                OVER (PARTITION BY code ORDER BY date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS limit_up_count_5d,
            SUM(CASE WHEN change_percent + 0.15 >= limit_threshold THEN 1 ELSE 0 END)
                OVER (PARTITION BY code ORDER BY date ROWS BETWEEN 9 PRECEDING AND CURRENT ROW) AS limit_up_count_10d,
            SUM(CASE WHEN change_percent + 0.15 >= limit_threshold THEN 1 ELSE 0 END)
                OVER (PARTITION BY code ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS limit_up_count_20d
        FROM base
    ),
    ranked AS (
        SELECT
            *,
            ROW_NUMBER() OVER (PARTITION BY code ORDER BY date DESC) AS rn,
            COUNT(*) OVER (PARTITION BY code) AS bar_count
        FROM scored
    ),
    history AS (
        SELECT
            code,
            STRING_AGG(CAST(close AS VARCHAR), ',' ORDER BY rn) AS close_history
        FROM ranked
        WHERE rn <= 233
        GROUP BY code
    )
    SELECT
        r.code,
        r.date,
        r.close,
        r.amount,
        r.change_percent,
        r.name,
        r.market,
        r.board,
        r.is_st,
        r.industry,
        r.ma5,
        r.ma10,
        r.ma20,
        r.ma30,
        r.ma60,
        r.ma120,
        r.ma233,
        r.return_5d,
        r.return_10d,
        r.return_20d,
        r.return_30d,
        r.return_60d,
        r.return_120d,
        r.return_233d,
        r.close_above_ma20,
        r.close_above_ma60,
        r.volume_ratio_20d,
        r.limit_up_count_5d,
        r.limit_up_count_10d,
        r.limit_up_count_20d,
        r.bar_count,
        h.close_history
    FROM ranked r
    LEFT JOIN history h ON h.code = r.code
    WHERE r.rn = 1;
    """)
    conn.execute("DROP TABLE IF EXISTS daily_bars;")
    conn.execute("DROP TABLE IF EXISTS minute_bars;")
    return conn.execute("SELECT COUNT(*) FROM daily_features;").fetchone()[0]


def compare_value(actual: Any, operator: str, expected: Any) -> bool:
    if actual is None or pd.isna(actual):
        return False
    if operator == "eq":
        return actual == expected
    if operator == "gt":
        return actual > expected
    if operator == "gte":
        return actual >= expected
    if operator == "lt":
        return actual < expected
    if operator == "lte":
        return actual <= expected
    if operator == "neq":
        return actual != expected
    raise ValueError(f"Unsupported operator: {operator}")


def passes_filters(row: pd.Series, filters: Dict[str, Any]) -> bool:
    if filters.get("exclude_st", False) and int(row.get("is_st") or 0) == 1:
        return False
    min_close = filters.get("min_close")
    if min_close is not None and not compare_value(row.get("close"), "gte", min_close):
        return False
    min_amount = filters.get("min_amount")
    if min_amount is not None and not compare_value(row.get("amount"), "gte", min_amount):
        return False
    max_change = filters.get("max_change_percent")
    if max_change is not None and not compare_value(row.get("change_percent"), "lte", max_change):
        return False
    if filters.get("require_ma20", False) and not bool(row.get("close_above_ma20")):
        return False
    return True


def evaluate_strategy(
    features: pd.DataFrame,
    strategy: Dict[str, Any],
    as_of_date: str,
    top: int,
    min_score_override: Optional[int],
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    filters = strategy.get("filters") or {}
    score_rules = strategy.get("score_rules") or []
    min_score = min_score_override if min_score_override is not None else int(strategy.get("min_score") or 0)

    latest = features[features["date"] == as_of_date].copy()
    for _, row in latest.iterrows():
        if not passes_filters(row, filters):
            continue

        score = 0
        matched_rules: List[str] = []
        matched_rule_ids: List[str] = []
        for rule in score_rules:
            if compare_value(row.get(rule.get("field")), rule.get("operator", "eq"), rule.get("value")):
                score += int(rule.get("points") or 0)
                matched_rules.append(rule.get("label") or rule.get("id") or rule.get("field"))
                matched_rule_ids.append(rule.get("id") or rule.get("field"))

        if score < min_score:
            continue

        rows.append({
            "run_id": "",
            "strategy_id": strategy.get("id"),
            "strategy_name": strategy.get("name"),
            "date": as_of_date,
            "code": row.get("code"),
            "name": row.get("code") if is_missing_stock_name(row.get("name"), row.get("code")) else row.get("name"),
            "score": score,
            "close": row.get("close"),
            "change_percent": row.get("change_percent"),
            "amount": row.get("amount"),
            "industry": row.get("industry"),
            "matched_rules": matched_rules,
            "matched_rule_ids": matched_rule_ids,
            "buy_reason": " ".join(strategy.get("buy_templates") or []),
            "sell_plan": " ".join(strategy.get("sell_templates") or []),
            "risk_notes": " ".join(strategy.get("risk_templates") or []),
            "feature_snapshot": {
                key: row.get(key)
                for key in [
                    "ma5", "ma10", "ma20", "ma30", "ma60", "ma120", "ma233",
                    "return_5d", "return_10d", "return_20d", "return_30d",
                    "return_60d", "return_120d", "return_233d",
                    "volume_ratio_20d", "limit_up_count_5d",
                    "limit_up_count_10d", "limit_up_count_20d"
                ]
            }
        })

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result = result.sort_values(["score", "amount"], ascending=[False, False]).head(top).copy()
    return result


def ensure_sqlite_strategy_tables(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS strategy_runs (
        run_id TEXT PRIMARY KEY,
        strategy_id TEXT NOT NULL,
        strategy_name TEXT NOT NULL,
        as_of_date TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT NOT NULL,
        source_sqlite_path TEXT,
        duckdb_path TEXT,
        stock_count INTEGER,
        bar_count INTEGER,
        feature_count INTEGER,
        result_count INTEGER,
        strategy_json TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS strategy_results (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        strategy_id TEXT NOT NULL,
        strategy_name TEXT NOT NULL,
        date TEXT NOT NULL,
        code TEXT NOT NULL,
        name TEXT,
        score INTEGER,
        close REAL,
        change_percent REAL,
        amount REAL,
        industry TEXT,
        matched_rules TEXT,
        matched_rule_ids TEXT,
        buy_reason TEXT,
        sell_plan TEXT,
        risk_notes TEXT,
        feature_snapshot TEXT,
        created_at TEXT
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_strategy_results_run ON strategy_results(run_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_strategy_results_date_score ON strategy_results(date, score DESC);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_strategy_results_code ON strategy_results(code);")
    conn.commit()


def write_results(
    sqlite_path: str,
    duck_conn: duckdb.DuckDBPyConnection,
    results: pd.DataFrame,
    strategy: Dict[str, Any],
    run_id: str,
    as_of_date: str,
    started_at: str,
    finished_at: str,
    sqlite_source: str,
    duckdb_path: str,
    stock_count: int,
    bar_count: int,
    feature_count: int,
) -> None:
    output = results.copy()
    created_at = finished_at
    if output.empty:
        output = pd.DataFrame(columns=[
            "id", "run_id", "strategy_id", "strategy_name", "date", "code", "name",
            "score", "close", "change_percent", "amount", "industry", "matched_rules",
            "matched_rule_ids", "buy_reason", "sell_plan", "risk_notes",
            "feature_snapshot", "created_at"
        ])
    else:
        output["run_id"] = run_id
        output["id"] = output.apply(lambda r: f"{run_id}_{r['code']}", axis=1)
        output["matched_rules"] = output["matched_rules"].map(json_text)
        output["matched_rule_ids"] = output["matched_rule_ids"].map(json_text)
        output["feature_snapshot"] = output["feature_snapshot"].map(json_text)
        output["created_at"] = created_at
        output = output[[
            "id", "run_id", "strategy_id", "strategy_name", "date", "code", "name",
            "score", "close", "change_percent", "amount", "industry", "matched_rules",
            "matched_rule_ids", "buy_reason", "sell_plan", "risk_notes",
            "feature_snapshot", "created_at"
        ]]

    duck_conn.register("strategy_results_df", output)
    duck_conn.execute("CREATE OR REPLACE TABLE strategy_results AS SELECT * FROM strategy_results_df;")
    duck_conn.unregister("strategy_results_df")

    with sqlite3.connect(sqlite_path) as sql_conn:
        ensure_sqlite_strategy_tables(sql_conn)
        cur = sql_conn.cursor()
        cur.execute("""
        INSERT OR REPLACE INTO strategy_runs
        (run_id, strategy_id, strategy_name, as_of_date, started_at, finished_at,
         source_sqlite_path, duckdb_path, stock_count, bar_count, feature_count,
         result_count, strategy_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            run_id,
            strategy.get("id"),
            strategy.get("name"),
            as_of_date,
            started_at,
            finished_at,
            sqlite_source,
            duckdb_path,
            stock_count,
            bar_count,
            feature_count,
            len(output),
            json_text(strategy),
        ))
        cur.execute("DELETE FROM strategy_results WHERE strategy_id = ? AND date = ?;", (strategy.get("id"), as_of_date))
        for row in output.itertuples(index=False):
            cur.execute("""
            INSERT OR REPLACE INTO strategy_results
            (id, run_id, strategy_id, strategy_name, date, code, name, score, close,
             change_percent, amount, industry, matched_rules, matched_rule_ids,
             buy_reason, sell_plan, risk_notes, feature_snapshot, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, tuple(row))
        sql_conn.commit()


def resolve_strategy_file(strategy_dir: str, strategy_file: Optional[str]) -> str:
    if strategy_file:
        if os.path.isabs(strategy_file):
            return strategy_file
        if os.path.exists(strategy_file):
            return os.path.abspath(strategy_file)
        return os.path.join(strategy_dir, strategy_file)
    candidates = [
        os.path.join(strategy_dir, filename)
        for filename in sorted(os.listdir(strategy_dir))
        if filename.endswith(".json")
    ]
    if not candidates:
        raise FileNotFoundError(f"No strategy JSON found in {strategy_dir}")
    return candidates[0]


def quote_duckdb_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def compact_duckdb_cache(source_path: str, target_path: str) -> None:
    if os.path.exists(target_path):
        os.remove(target_path)

    conn = duckdb.connect(target_path)
    try:
        conn.execute(f"ATTACH {quote_duckdb_string(source_path)} AS src (READ_ONLY)")
        for table_name in ["stocks", "daily_features", "strategy_results"]:
            try:
                conn.execute(f'CREATE TABLE "{table_name}" AS SELECT * FROM src."{table_name}"')
            except duckdb.CatalogException:
                continue
        conn.execute("CHECKPOINT")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build DuckDB analysis tables and SQLite strategy results.")
    parser.add_argument("--sqlite-path", default=DEFAULT_SQLITE_PATH)
    parser.add_argument("--duckdb-path", default=DEFAULT_DUCKDB_PATH)
    parser.add_argument("--strategy-dir", default=DEFAULT_STRATEGY_DIR)
    parser.add_argument("--strategy-file", default=None)
    parser.add_argument("--as-of-date", default="latest")
    parser.add_argument("--top", type=int, default=50)
    parser.add_argument("--limit-codes", type=int, default=0)
    parser.add_argument("--min-score", type=int, default=None)
    args = parser.parse_args()

    strategy_path = resolve_strategy_file(args.strategy_dir, args.strategy_file)
    if not os.path.exists(args.sqlite_path):
        raise FileNotFoundError(f"SQLite database not found: {args.sqlite_path}")
    if not os.path.exists(strategy_path):
        raise FileNotFoundError(f"Strategy file not found: {strategy_path}")

    os.makedirs(os.path.dirname(args.duckdb_path), exist_ok=True)
    rebuild_duckdb_path = f"{args.duckdb_path}.rebuilding"
    compact_duckdb_path = f"{args.duckdb_path}.compact"
    if os.path.exists(rebuild_duckdb_path):
        os.remove(rebuild_duckdb_path)
    if os.path.exists(compact_duckdb_path):
        os.remove(compact_duckdb_path)
    strategy = load_strategy(strategy_path)
    started_at = now_ts()
    run_id = f"{strategy.get('id', 'strategy')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    conn = duckdb.connect(rebuild_duckdb_path)
    try:
        init_duckdb_schema(conn)
        stock_count, bar_count = sync_source_tables(conn, args.sqlite_path, args.limit_codes)
        feature_count = build_daily_features(conn)
        as_of_date = args.as_of_date
        if as_of_date == "latest":
            as_of_date = conn.execute("SELECT MAX(date) FROM daily_features;").fetchone()[0]

        features = conn.execute("SELECT * FROM daily_features WHERE date = ?;", [as_of_date]).df()
        results = evaluate_strategy(features, strategy, as_of_date, args.top, args.min_score)
        finished_at = now_ts()
        write_results(
            args.sqlite_path,
            conn,
            results,
            strategy,
            run_id,
            as_of_date,
            started_at,
            finished_at,
            args.sqlite_path,
            args.duckdb_path,
            stock_count,
            bar_count,
            feature_count,
        )
    finally:
        conn.close()
    compact_duckdb_cache(rebuild_duckdb_path, compact_duckdb_path)
    os.replace(compact_duckdb_path, args.duckdb_path)
    if os.path.exists(rebuild_duckdb_path):
        os.remove(rebuild_duckdb_path)

    print(json.dumps({
        "run_id": run_id,
        "strategy": strategy.get("name"),
        "strategy_path": strategy_path,
        "sqlite_path": args.sqlite_path,
        "duckdb_path": args.duckdb_path,
        "as_of_date": as_of_date,
        "stock_count": stock_count,
        "bar_count": bar_count,
        "feature_count": feature_count,
        "result_count": int(len(results)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
