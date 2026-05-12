#!/usr/bin/env python3
"""Fetch StockMaster sector snapshots into DataCenter/sector_sources.sqlite.

The summary path intentionally uses AkShare because it exposes the full
TongHuaShun industry table as structured rows. Scrapling is kept in the detail
page path where HTML parsing and future anti-bot handling matter most.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd


SOURCE_THS = "ths"
THS_HOME = "https://q.10jqka.com.cn/thshy/"
THS_DETAIL = "https://q.10jqka.com.cn/thshy/detail/code/{code}/"
TIMEZONE_SUFFIX = "+08:00"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS data_sources (
    source TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    description TEXT,
    homepage_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sector_categories (
    source TEXT NOT NULL,
    category_code TEXT NOT NULL,
    category_name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (source, category_code),
    FOREIGN KEY (source) REFERENCES data_sources(source)
);

CREATE TABLE IF NOT EXISTS sectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_code TEXT NOT NULL,
    unified_code TEXT NOT NULL UNIQUE,
    category_code TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    source_url TEXT,
    fetched_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (source, source_code),
    FOREIGN KEY (source) REFERENCES data_sources(source),
    FOREIGN KEY (source, category_code) REFERENCES sector_categories(source, category_code)
);

CREATE TABLE IF NOT EXISTS sector_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_code TEXT NOT NULL,
    unified_code TEXT NOT NULL,
    snapshot_at TEXT NOT NULL,
    rank INTEGER,
    change_pct REAL,
    volume_wan_shou REAL,
    amount_yi REAL,
    net_inflow_yi REAL,
    up_count INTEGER,
    down_count INTEGER,
    avg_price REAL,
    leading_stock_code TEXT,
    leading_stock_name TEXT,
    leading_stock_price REAL,
    leading_stock_change_pct REAL,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (source, source_code, snapshot_at),
    FOREIGN KEY (source, source_code) REFERENCES sectors(source, source_code)
);

CREATE TABLE IF NOT EXISTS sector_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    sector_source_code TEXT NOT NULL,
    unified_sector_code TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    stock_name TEXT,
    rank INTEGER,
    price REAL,
    change_pct REAL,
    change_amount REAL,
    speed_pct REAL,
    turnover_pct REAL,
    volume_ratio REAL,
    amplitude_pct REAL,
    amount REAL,
    float_shares REAL,
    float_market_value REAL,
    pe REAL,
    snapshot_at TEXT NOT NULL,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (source, sector_source_code, stock_code, snapshot_at),
    FOREIGN KEY (source, sector_source_code) REFERENCES sectors(source, source_code)
);

CREATE TABLE IF NOT EXISTS fetch_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_code TEXT,
    url TEXT NOT NULL,
    http_status INTEGER,
    encoding TEXT,
    fetched_at TEXT NOT NULL,
    raw_path TEXT,
    row_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class FetchResult:
    status_code: int | None
    encoding: str | None
    text: str


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def snapshot_at_for(date_string: str) -> str:
    return f"{date_string}T15:30:00{TIMEZONE_SUFFIX}"


def resolve_effective_trade_date(date_string: str) -> tuple[str, bool]:
    """Return the requested A-share trade date or the closest previous one."""
    calendar_df = ak.tool_trade_date_hist_sina()
    trade_dates = sorted(clean_text(value) for value in calendar_df["trade_date"] if clean_text(value))
    if date_string in trade_dates:
        return date_string, True

    previous_dates = [value for value in trade_dates if value <= date_string]
    if not previous_dates:
        raise ValueError(f"No A-share trading day found before {date_string}")
    return previous_dates[-1], False


def default_data_center() -> Path:
    if value := os.environ.get("STOCKMASTER_DATA_CENTER"):
        return Path(value).expanduser()
    if value := os.environ.get("STOCKMASTER_ROOT"):
        return Path(value).expanduser() / "DataCenter"
    return Path.cwd() / "DataCenter"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch sector data for StockMaster")
    parser.add_argument("--date", required=True, help="Trading date, format YYYY-MM-DD")
    parser.add_argument("--source", default=SOURCE_THS, choices=[SOURCE_THS], help="Data source")
    parser.add_argument("--category", default="industry", choices=["industry"], help="Sector category")
    parser.add_argument("--db", help="SQLite output path. Defaults to STOCKMASTER_DATA_CENTER/sector_sources.sqlite")
    parser.add_argument("--summary-only", action="store_true", help="Only fetch daily summary snapshots")
    parser.add_argument("--with-components", action="store_true", help="Fetch detail page component rows")
    parser.add_argument("--sector-code", help="Limit component fetch to one sector code")
    parser.add_argument("--component-limit", type=int, default=0, help="Limit component detail requests, mainly for smoke tests")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary")
    args = parser.parse_args()

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        parser.error("--date must use YYYY-MM-DD")
    if args.component_limit < 0:
        parser.error("--component-limit must be non-negative")
    return args


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def optional_float(value: Any) -> float | None:
    text = clean_text(value)
    if not text or text in {"-", "--"}:
        return None
    text = text.replace(",", "").replace("%", "").strip()
    multiplier = 1.0
    if text.endswith("万亿"):
        multiplier = 10000.0
        text = text[:-2]
    elif text.endswith("亿"):
        text = text[:-1]
    elif text.endswith("万"):
        multiplier = 0.0001
        text = text[:-1]
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def optional_int(value: Any) -> int | None:
    number = optional_float(value)
    if number is None:
        return None
    result = int(number)
    if result < 0:
        raise ValueError(f"Count must be non-negative: {value!r}")
    return result


def normalize_stock_code(value: Any) -> str | None:
    text = clean_text(value)
    match = re.search(r"\b(\d{6})\b", text)
    return match.group(1) if match else None


def dataframe_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for record in df.to_dict(orient="records"):
        cleaned: dict[str, Any] = {}
        for key, value in record.items():
            if pd.isna(value):
                cleaned[str(key)] = None
            elif hasattr(value, "item"):
                cleaned[str(key)] = value.item()
            else:
                cleaned[str(key)] = value
        records.append(cleaned)
    return records


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")


def upsert_source_metadata(conn: sqlite3.Connection, fetched_at: str) -> None:
    conn.execute(
        """
        INSERT INTO data_sources(source, display_name, description, homepage_url, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(source) DO UPDATE SET
            display_name = excluded.display_name,
            description = excluded.description,
            homepage_url = excluded.homepage_url,
            updated_at = excluded.updated_at
        """,
        (SOURCE_THS, "同花顺", "同花顺行业、概念等板块数据源", THS_HOME, fetched_at, fetched_at),
    )
    categories = [
        ("industry", "同花顺行业", "同花顺行业板块"),
        ("concept", "同花顺概念", "同花顺概念板块"),
    ]
    for category_code, category_name, description in categories:
        conn.execute(
            """
            INSERT INTO sector_categories(source, category_code, category_name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, category_code) DO UPDATE SET
                category_name = excluded.category_name,
                description = excluded.description,
                updated_at = excluded.updated_at
            """,
            (SOURCE_THS, category_code, category_name, description, fetched_at, fetched_at),
        )


def fetch_ths_summary() -> tuple[pd.DataFrame, dict[str, str]]:
    summary_df = ak.stock_board_industry_summary_ths()
    names_df = ak.stock_board_industry_name_ths()
    code_by_name = {
        clean_text(row["name"]): clean_text(row["code"])
        for _, row in names_df.iterrows()
        if clean_text(row.get("name")) and clean_text(row.get("code"))
    }
    return summary_df, code_by_name


def upsert_ths_summary(
    conn: sqlite3.Connection,
    summary_df: pd.DataFrame,
    code_by_name: dict[str, str],
    date_string: str,
    fetched_at: str,
) -> int:
    snapshot_at = snapshot_at_for(date_string)
    rows = dataframe_records(summary_df)
    written = 0

    # Sector data is consumed by trading day in the App. Replace the previous
    # same-day snapshot to avoid mixing an old top-50 scrape with a full close
    # snapshot from the same source/category.
    conn.execute(
        """
        DELETE FROM sector_snapshots
        WHERE source = ?
          AND substr(snapshot_at, 1, 10) = ?
          AND EXISTS (
              SELECT 1
              FROM sectors s
              WHERE s.source = sector_snapshots.source
                AND s.source_code = sector_snapshots.source_code
                AND s.category_code = 'industry'
          )
        """,
        (SOURCE_THS, date_string),
    )

    for row in rows:
        name = clean_text(row.get("板块"))
        if not name:
            continue
        source_code = code_by_name.get(name)
        if not source_code:
            continue

        unified_code = f"{SOURCE_THS}:{source_code}"
        source_url = THS_DETAIL.format(code=source_code)
        rank = optional_int(row.get("序号"))
        up_count = optional_int(row.get("上涨家数"))
        down_count = optional_int(row.get("下跌家数"))

        conn.execute(
            """
            INSERT INTO sectors(
                source, source_code, unified_code, category_code, name, description,
                source_url, fetched_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, source_code) DO UPDATE SET
                unified_code = excluded.unified_code,
                category_code = excluded.category_code,
                name = excluded.name,
                source_url = excluded.source_url,
                fetched_at = excluded.fetched_at,
                updated_at = excluded.updated_at
            """,
            (SOURCE_THS, source_code, unified_code, "industry", name, None, source_url, fetched_at, fetched_at, fetched_at),
        )

        conn.execute(
            """
            INSERT INTO sector_snapshots(
                source, source_code, unified_code, snapshot_at, rank, change_pct,
                volume_wan_shou, amount_yi, net_inflow_yi, up_count, down_count,
                avg_price, leading_stock_code, leading_stock_name, leading_stock_price,
                leading_stock_change_pct, raw_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, source_code, snapshot_at) DO UPDATE SET
                unified_code = excluded.unified_code,
                rank = excluded.rank,
                change_pct = excluded.change_pct,
                volume_wan_shou = excluded.volume_wan_shou,
                amount_yi = excluded.amount_yi,
                net_inflow_yi = excluded.net_inflow_yi,
                up_count = excluded.up_count,
                down_count = excluded.down_count,
                avg_price = excluded.avg_price,
                leading_stock_code = excluded.leading_stock_code,
                leading_stock_name = excluded.leading_stock_name,
                leading_stock_price = excluded.leading_stock_price,
                leading_stock_change_pct = excluded.leading_stock_change_pct,
                raw_json = excluded.raw_json,
                created_at = excluded.created_at
            """,
            (
                SOURCE_THS,
                source_code,
                unified_code,
                snapshot_at,
                rank,
                optional_float(row.get("涨跌幅")),
                optional_float(row.get("总成交量")),
                optional_float(row.get("总成交额")),
                optional_float(row.get("净流入")),
                up_count,
                down_count,
                optional_float(row.get("均价")),
                normalize_stock_code(row.get("领涨股")),
                clean_text(row.get("领涨股")) or None,
                optional_float(row.get("领涨股-最新价")),
                optional_float(row.get("领涨股-涨跌幅")),
                json.dumps(row, ensure_ascii=False),
                fetched_at,
            ),
        )
        written += 1

    conn.execute(
        """
        INSERT INTO fetch_audit(source, target_type, target_code, url, http_status, encoding, fetched_at, raw_path, row_count, error, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (SOURCE_THS, "sector_summary", None, THS_HOME, 200, "akshare", fetched_at, None, written, None, fetched_at),
    )
    return written


def delete_ths_day_data(conn: sqlite3.Connection, date_string: str) -> None:
    """Remove stale same-day THS industry data before non-trading fallback writes."""
    conn.execute(
        """
        DELETE FROM sector_components
        WHERE source = ?
          AND substr(snapshot_at, 1, 10) = ?
          AND sector_source_code IN (
              SELECT source_code
              FROM sectors
              WHERE source = ?
                AND category_code = 'industry'
          )
        """,
        (SOURCE_THS, date_string, SOURCE_THS),
    )
    conn.execute(
        """
        DELETE FROM sector_snapshots
        WHERE source = ?
          AND substr(snapshot_at, 1, 10) = ?
          AND source_code IN (
              SELECT source_code
              FROM sectors
              WHERE source = ?
                AND category_code = 'industry'
          )
        """,
        (SOURCE_THS, date_string, SOURCE_THS),
    )


def count_ths_summary_rows(conn: sqlite3.Connection, date_string: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(DISTINCT ss.source_code)
        FROM sector_snapshots ss
        JOIN sectors s
          ON s.source = ss.source AND s.source_code = ss.source_code
        WHERE ss.source = ?
          AND s.category_code = 'industry'
          AND substr(ss.snapshot_at, 1, 10) = ?
        """,
        (SOURCE_THS, date_string),
    ).fetchone()
    return int(row[0] or 0) if row else 0


def normalize_sqlite_journal(db_path: Path) -> str | None:
    """Keep the App-facing sector DB independent from WAL sidecar files."""
    try:
        with sqlite3.connect(db_path, timeout=10) as conn:
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("PRAGMA journal_mode = DELETE")
            conn.execute("PRAGMA optimize")
        return None
    except sqlite3.OperationalError as exc:
        return f"journal cleanup skipped: {exc}"


def fetch_page_text(url: str) -> FetchResult:
    try:
        from scrapling.fetchers import Fetcher  # type: ignore

        page = Fetcher.get(url, stealthy_headers=True, timeout=30)
        text = getattr(page, "text", None) or str(page)
        status = getattr(page, "status", None) or getattr(page, "status_code", None)
        encoding = getattr(page, "encoding", None)
        return FetchResult(status, encoding, text)
    except Exception:
        import requests

        response = requests.get(
            url,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Referer": THS_HOME,
            },
        )
        response.encoding = response.apparent_encoding or "gbk"
        return FetchResult(response.status_code, response.encoding, response.text)


def parse_component_rows(html: str) -> list[dict[str, Any]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    for table in soup.find_all("table"):
        headers = [cell.get_text("", strip=True) for cell in table.find_all("th")]
        if "代码" not in headers or "名称" not in headers:
            continue
        rows: list[dict[str, Any]] = []
        for tr in table.find_all("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["td", "th"])]
            if not cells or cells == headers or len(cells) < 3:
                continue
            stock_code = normalize_stock_code(cells[1])
            if not stock_code:
                continue
            rows.append(
                {
                    "rank": optional_int(cells[0]),
                    "stock_code": stock_code,
                    "stock_name": clean_text(cells[2]),
                    "price": optional_float(cells[3] if len(cells) > 3 else None),
                    "change_pct": optional_float(cells[4] if len(cells) > 4 else None),
                    "change_amount": optional_float(cells[5] if len(cells) > 5 else None),
                    "speed_pct": optional_float(cells[6] if len(cells) > 6 else None),
                    "turnover_pct": optional_float(cells[7] if len(cells) > 7 else None),
                    "volume_ratio": optional_float(cells[8] if len(cells) > 8 else None),
                    "amplitude_pct": optional_float(cells[9] if len(cells) > 9 else None),
                    "amount": optional_float(cells[10] if len(cells) > 10 else None),
                    "float_shares": optional_float(cells[11] if len(cells) > 11 else None),
                    "float_market_value": optional_float(cells[12] if len(cells) > 12 else None),
                    "pe": optional_float(cells[13] if len(cells) > 13 else None),
                    "raw": cells,
                }
            )
        return rows
    return []


def upsert_components(
    conn: sqlite3.Connection,
    sectors: list[tuple[str, str]],
    date_string: str,
    fetched_at: str,
    component_limit: int,
) -> int:
    snapshot_at = snapshot_at_for(date_string)
    selected = sectors[:component_limit] if component_limit else sectors
    written = 0
    selected_codes = [source_code for source_code, _ in selected]

    if selected_codes:
        placeholders = ",".join("?" for _ in selected_codes)
        conn.execute(
            f"""
            DELETE FROM sector_components
            WHERE source = ?
              AND substr(snapshot_at, 1, 10) = ?
              AND sector_source_code IN ({placeholders})
            """,
            [SOURCE_THS, date_string, *selected_codes],
        )

    for source_code, unified_code in selected:
        url = THS_DETAIL.format(code=source_code)
        error: str | None = None
        status: int | None = None
        encoding: str | None = None
        rows: list[dict[str, Any]] = []
        try:
            result = fetch_page_text(url)
            status = result.status_code
            encoding = result.encoding
            rows = parse_component_rows(result.text)
            for row in rows:
                conn.execute(
                    """
                    INSERT INTO sector_components(
                        source, sector_source_code, unified_sector_code, stock_code, stock_name,
                        rank, price, change_pct, change_amount, speed_pct, turnover_pct,
                        volume_ratio, amplitude_pct, amount, float_shares, float_market_value,
                        pe, snapshot_at, raw_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source, sector_source_code, stock_code, snapshot_at) DO UPDATE SET
                        unified_sector_code = excluded.unified_sector_code,
                        stock_name = excluded.stock_name,
                        rank = excluded.rank,
                        price = excluded.price,
                        change_pct = excluded.change_pct,
                        change_amount = excluded.change_amount,
                        speed_pct = excluded.speed_pct,
                        turnover_pct = excluded.turnover_pct,
                        volume_ratio = excluded.volume_ratio,
                        amplitude_pct = excluded.amplitude_pct,
                        amount = excluded.amount,
                        float_shares = excluded.float_shares,
                        float_market_value = excluded.float_market_value,
                        pe = excluded.pe,
                        raw_json = excluded.raw_json,
                        created_at = excluded.created_at
                    """,
                    (
                        SOURCE_THS,
                        source_code,
                        unified_code,
                        row["stock_code"],
                        row["stock_name"],
                        row["rank"],
                        row["price"],
                        row["change_pct"],
                        row["change_amount"],
                        row["speed_pct"],
                        row["turnover_pct"],
                        row["volume_ratio"],
                        row["amplitude_pct"],
                        row["amount"],
                        row["float_shares"],
                        row["float_market_value"],
                        row["pe"],
                        snapshot_at,
                        json.dumps(row["raw"], ensure_ascii=False),
                        fetched_at,
                    ),
                )
            written += len(rows)
        except Exception as exc:  # Keep other boards moving and audit the failed page.
            error = str(exc)

        conn.execute(
            """
            INSERT INTO fetch_audit(source, target_type, target_code, url, http_status, encoding, fetched_at, raw_path, row_count, error, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (SOURCE_THS, "sector_components", source_code, url, status, encoding, fetched_at, None, len(rows), error, fetched_at),
        )

    return written


def sector_codes_for_components(
    conn: sqlite3.Connection,
    sector_code: str | None,
) -> list[tuple[str, str]]:
    sql = """
    SELECT source_code, unified_code
    FROM sectors
    WHERE source = ? AND category_code = 'industry'
    """
    params: list[Any] = [SOURCE_THS]
    if sector_code:
        sql += " AND source_code = ?"
        params.append(sector_code)
    sql += " ORDER BY name"
    return [(row[0], row[1]) for row in conn.execute(sql, params).fetchall()]


def main() -> int:
    args = parse_args()
    effective_date, is_trading_day = resolve_effective_trade_date(args.date)
    db_path = Path(args.db).expanduser() if args.db else default_data_center() / "sector_sources.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    fetched_at = now_iso()

    summary_count = 0
    component_count = 0
    journal_warning: str | None = None
    with sqlite3.connect(db_path, timeout=10) as conn:
        init_db(conn)
        upsert_source_metadata(conn, fetched_at)

        if args.source == SOURCE_THS:
            existing_effective_rows = count_ths_summary_rows(conn, effective_date)
            if effective_date != args.date and existing_effective_rows > 0:
                delete_ths_day_data(conn, args.date)
                summary_count = existing_effective_rows
            else:
                summary_df, code_by_name = fetch_ths_summary()
                if effective_date != args.date:
                    delete_ths_day_data(conn, args.date)
                summary_count = upsert_ths_summary(conn, summary_df, code_by_name, effective_date, fetched_at)

            should_fetch_components = args.with_components and not args.summary_only
            if should_fetch_components:
                sectors = sector_codes_for_components(conn, args.sector_code)
                component_count = upsert_components(conn, sectors, effective_date, fetched_at, args.component_limit)

        conn.commit()

    journal_warning = normalize_sqlite_journal(db_path)

    result = {
        "ok": True,
        "source": args.source,
        "requested_date": args.date,
        "effective_date": effective_date,
        "is_trading_day": is_trading_day,
        "date": effective_date,
        "db": str(db_path),
        "summary_rows": summary_count,
        "component_rows": component_count,
        "fetched_at": fetched_at,
        "warning": journal_warning,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        if is_trading_day:
            print(f"板块数据刷新完成: {args.source} {effective_date}, 行情快照 {summary_count} 条, 成分股 {component_count} 条")
        else:
            print(
                f"{args.date} 非 A 股交易日，已使用最后交易日 {effective_date}: "
                f"行情快照 {summary_count} 条, 成分股 {component_count} 条"
            )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"sector fetch failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
