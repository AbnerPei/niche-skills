#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import argparse
import sqlite3
import time
import random
import concurrent.futures
import importlib.util
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
SKILLS_ROOT = os.path.abspath(os.path.join(SKILL_ROOT, ".."))
PROJECT_DIR = os.environ.get("STOCKMASTER_ROOT", os.path.abspath(os.path.join(SKILLS_ROOT, "..", "StockMaster")))
ROOT_DIR = os.path.join(PROJECT_DIR, "StockMaster")
DATACENTER_DIR = os.path.join(ROOT_DIR, "DataCenter")
DEFAULT_DB_PATH = os.path.join(DATACENTER_DIR, "market.sqlite")
COMPANY_META_PATH = os.path.join(DATACENTER_DIR, "companies_metadata.json")

def resolve_fetch_single_path():
    candidates = [
        os.environ.get("STOCKMASTER_FETCH_SINGLE_SCRIPT"),
        os.path.join(SKILLS_ROOT, "stockmaster-stock-history", "scripts", "fetch_single_stock.py"),
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return candidates[0] or candidates[1]

FETCH_SINGLE_PATH = resolve_fetch_single_path()

def now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def load_fetch_single_module():
    if not os.path.exists(FETCH_SINGLE_PATH):
        raise FileNotFoundError(
            "fetch_single_stock.py not found. Set STOCKMASTER_FETCH_SINGLE_SCRIPT "
            "or install stockmaster-stock-history next to stockmaster-market-db."
        )
    spec = importlib.util.spec_from_file_location("fetch_single_stock", FETCH_SINGLE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def connect_db(db_path: str):
    ensure_dir(os.path.dirname(db_path))
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS stocks (
        code TEXT PRIMARY KEY,
        name TEXT,
        market TEXT,
        market_id INTEGER,
        board TEXT,
        is_st INTEGER,
        industry TEXT,
        area TEXT,
        listed_at TEXT,
        status TEXT,
        updated_at TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_bars (
        code TEXT NOT NULL,
        date TEXT NOT NULL,
        open REAL,
        close REAL,
        high REAL,
        low REAL,
        volume REAL,
        amount REAL,
        amplitude REAL,
        change_percent REAL,
        change_amount REAL,
        turnover_rate REAL,
        PRIMARY KEY (code, date)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_bars_code ON daily_bars(code);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_bars_date ON daily_bars(date);")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS fetch_status (
        code TEXT PRIMARY KEY,
        last_success_date TEXT,
        last_attempt_at TEXT,
        error TEXT,
        attempts INTEGER DEFAULT 0,
        last_rows INTEGER DEFAULT 0
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)
    cur.execute("PRAGMA table_info(stocks);")
    cols = {r[1] for r in cur.fetchall()}
    if "market_id" not in cols:
        cur.execute("ALTER TABLE stocks ADD COLUMN market_id INTEGER;")
    cur.execute("PRAGMA table_info(fetch_status);")
    cols2 = {r[1] for r in cur.fetchall()}
    if "attempts" not in cols2:
        cur.execute("ALTER TABLE fetch_status ADD COLUMN attempts INTEGER DEFAULT 0;")
    if "last_rows" not in cols2:
        cur.execute("ALTER TABLE fetch_status ADD COLUMN last_rows INTEGER DEFAULT 0;")
    conn.commit()

def get_random_headers():
    uas = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ]
    return {"User-Agent": random.choice(uas), "Accept": "*/*", "Accept-Language": "zh-CN,zh;q=0.9", "Connection": "keep-alive"}

def fetch_stock_list_from_eastmoney() -> List[Dict[str, Any]]:
    hosts = ["http://82.push2.eastmoney.com", "http://87.push2.eastmoney.com", "http://18.push2.eastmoney.com"]
    # fs 参数组合：沪深京 A股（尽量覆盖）
    fs_list = [
        "m:1 t:2",  # 上证A
        "m:0 t:6",  # 深证A
        "m:0 t:80", # 创业板
        "m:1 t:23", # 科创板
        "m:0 t:81"  # 北交所（部分环境返回 market_id=0/2/??，以 f13 为准）
    ]
    fields = "f12,f13,f14"
    all_rows = {}

    def fetch_one(host: str, fs: str, pn: int, pz: int) -> Optional[Dict[str, Any]]:
        url = f"{host}/api/qt/clist/get"
        params = {
            "pn": str(pn),
            "pz": str(pz),
            "po": "1",
            "np": "1",
            "fltt": "2",
            "fid": "f12",
            "fs": fs,
            "fields": fields
        }
        r = requests.get(url, params=params, headers=get_random_headers(), timeout=8)
        if r.status_code != 200:
            return None
        return r.json()

    pz = 2000
    for fs in fs_list:
        data = None
        for host in hosts:
            try:
                data = fetch_one(host, fs, 1, pz)
                if data and data.get("data") and "diff" in data["data"]:
                    break
            except Exception:
                data = None
        if not data or not data.get("data") or "diff" not in data["data"]:
            continue
        total = int(data["data"].get("total") or 0)
        pages = max(1, (total + pz - 1) // pz) if total else 1
        for row in data["data"]["diff"]:
            code = row.get("f12")
            market_id = row.get("f13")
            name = row.get("f14")
            if not code or not name or market_id is None:
                continue
            all_rows[code] = {
                "code": code,
                "name": name,
                "market": "SSE" if market_id == 1 else "SZSE" if market_id == 0 else None,
                "market_id": int(market_id),
                "board": None,
                "is_st": 1 if ("ST" in name or "＊ST" in name or "∗ST" in name) else 0,
                "industry": None,
                "area": None,
                "listed_at": None,
                "status": "active"
            }
        if pages <= 1:
            continue
        for pn in range(2, pages + 1):
            data2 = None
            for host in hosts:
                try:
                    data2 = fetch_one(host, fs, pn, pz)
                    if data2 and data2.get("data") and "diff" in data2["data"]:
                        break
                except Exception:
                    data2 = None
            if not data2 or not data2.get("data") or "diff" not in data2["data"]:
                continue
            for row in data2["data"]["diff"]:
                code = row.get("f12")
                market_id = row.get("f13")
                name = row.get("f14")
                if not code or not name or market_id is None:
                    continue
                all_rows[code] = {
                    "code": code,
                    "name": name,
                    "market": "SSE" if market_id == 1 else "SZSE" if market_id == 0 else None,
                    "market_id": int(market_id),
                    "board": None,
                    "is_st": 1 if ("ST" in name or "＊ST" in name or "∗ST" in name) else 0,
                    "industry": None,
                    "area": None,
                    "listed_at": None,
                    "status": "active"
                }
    return list(all_rows.values())

def load_codes_from_metadata() -> List[Dict[str, Any]]:
    try:
        with open(COMPANY_META_PATH, "r", encoding="utf-8") as f:
            obj = json.load(f)
        items = []
        for code, meta in obj.items():
            items.append({
                "code": code,
                "name": meta.get("name") or code,
                "market": None,
                "board": None,
                "is_st": 0,
                "industry": meta.get("industry"),
                "area": meta.get("area"),
                "listed_at": None,
                "status": "active"
            })
        return items
    except Exception:
        return []

def upsert_stocks(conn: sqlite3.Connection, stocks: List[Dict[str, Any]]):
    cur = conn.cursor()
    for s in stocks:
        cur.execute("""
        INSERT INTO stocks(code,name,market,market_id,board,is_st,industry,area,listed_at,status,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(code) DO UPDATE SET
            name=excluded.name,
            market=COALESCE(excluded.market,stocks.market),
            market_id=COALESCE(excluded.market_id,stocks.market_id),
            board=COALESCE(excluded.board,stocks.board),
            is_st=excluded.is_st,
            industry=COALESCE(excluded.industry,stocks.industry),
            area=COALESCE(excluded.area,stocks.area),
            listed_at=COALESCE(excluded.listed_at,stocks.listed_at),
            status=excluded.status,
            updated_at=excluded.updated_at;
        """, (
            s.get("code"),
            s.get("name"),
            s.get("market"),
            s.get("market_id"),
            s.get("board"),
            s.get("is_st", 0),
            s.get("industry"),
            s.get("area"),
            s.get("listed_at"),
            s.get("status", "active"),
            now_ts()
        ))
    conn.commit()

def fetch_with_retry(func, *args, retries=3, backoff_min=0.5, backoff_max=1.5, **kwargs):
    for attempt in range(retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt >= retries:
                raise
            time.sleep(random.uniform(backoff_min, backoff_max) * (attempt + 1))

def insert_bars(conn: sqlite3.Connection, code: str, bars: List[Dict[str, Any]]):
    cur = conn.cursor()
    rows = []
    for b in bars:
        rows.append((
            code,
            b.get("日期"),
            b.get("开盘价"),
            b.get("收盘价"),
            b.get("最高价"),
            b.get("最低价"),
            b.get("成交量"),
            b.get("成交额"),
            b.get("振幅"),
            b.get("涨跌幅"),
            b.get("涨跌额"),
            b.get("换手率"),
        ))
    cur.executemany("""
        INSERT OR REPLACE INTO daily_bars
        (code,date,open,close,high,low,volume,amount,amplitude,change_percent,change_amount,turnover_rate)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)

def update_status(conn: sqlite3.Connection, code: str, success_date: Optional[str], error: Optional[str], rows: int):
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO fetch_status(code,last_success_date,last_attempt_at,error,attempts,last_rows)
    VALUES(?,?,?,?,?,?)
    ON CONFLICT(code) DO UPDATE SET
        last_success_date=excluded.last_success_date,
        last_attempt_at=excluded.last_attempt_at,
        error=excluded.error,
        attempts=fetch_status.attempts+1,
        last_rows=excluded.last_rows;
    """, (code, success_date, now_ts(), error, 1, rows))
    conn.commit()

def normalize_date(date_str: str) -> str:
    return date_str.replace("/", "-").strip()

def to_yyyymmdd(date_str: str) -> str:
    return normalize_date(date_str).replace("-", "")

def parse_kline_strings(klines: List[str]) -> List[Dict[str, Any]]:
    bars = []
    for s in klines:
        parts = s.split(",")
        if len(parts) < 11:
            continue
        bars.append({
            "日期": parts[0],
            "开盘价": float(parts[1]) if parts[1] else None,
            "收盘价": float(parts[2]) if parts[2] else None,
            "最高价": float(parts[3]) if parts[3] else None,
            "最低价": float(parts[4]) if parts[4] else None,
            "成交量": float(parts[5]) if parts[5] else None,
            "成交额": float(parts[6]) if parts[6] else None,
            "振幅": float(parts[7]) if parts[7] else None,
            "涨跌幅": float(parts[8]) if parts[8] else None,
            "涨跌额": float(parts[9]) if parts[9] else None,
            "换手率": float(parts[10]) if parts[10] else None,
        })
    return bars

def fetch_kline_eastmoney_secid(secid: str, start_date: str) -> List[Dict[str, Any]]:
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "klt": "101",
        "fqt": "1",
        "secid": secid,
        "beg": to_yyyymmdd(start_date),
        "end": "20500101",
        "lmt": "100000"
    }
    r = requests.get(url, params=params, headers=get_random_headers(), timeout=12)
    r.raise_for_status()
    data = r.json()
    klines = (((data or {}).get("data") or {}).get("klines")) or []
    return parse_kline_strings(klines)

def get_latest_date(conn: sqlite3.Connection, code: str) -> Optional[str]:
    cur = conn.cursor()
    cur.execute("SELECT MAX(date) FROM daily_bars WHERE code = ?;", (code,))
    row = cur.fetchone()
    return row[0] if row and row[0] else None

def add_one_day(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return (d + timedelta(days=1)).strftime("%Y-%m-%d")

def process_code(db_path: str, code: str, market_id: int, start_date: str, retries: int, sleep_min: float, sleep_max: float):
    conn = connect_db(db_path)
    try:
        latest = get_latest_date(conn, code)
        effective_start = start_date
        if latest and latest >= start_date:
            effective_start = add_one_day(latest)
        secid = f"{market_id}.{code}"
        bars = fetch_with_retry(fetch_kline_eastmoney_secid, secid, effective_start, retries=retries)
        if bars:
            bars = [b for b in bars if (b.get("日期") or "") >= start_date]
            conn.execute("BEGIN;")
            insert_bars(conn, code, bars)
            conn.commit()
            last_date = max([b["日期"] for b in bars if b.get("日期")], default=None)
            update_status(conn, code, last_date, None, len(bars))
        else:
            if latest:
                update_status(conn, code, latest, None, 0)
            else:
                update_status(conn, code, None, "empty_bars", 0)
    except Exception as e:
        update_status(conn, code, None, str(e), 0)
    finally:
        try:
            conn.close()
        except Exception:
            pass
        if sleep_min > 0 or sleep_max > 0:
            time.sleep(random.uniform(sleep_min, max(sleep_min, sleep_max)))
    try:
        bars = fetch_with_retry(module.fetch_kline_eastmoney, code, start_date=start_date, retries=retries)
        if (not bars) and hasattr(module, "RealStockDataFetcher"):
            try:
                fetcher = module.RealStockDataFetcher(output_dir=os.path.join(os.path.dirname(FETCH_SINGLE_PATH), "real_time_data"))
                # 某些环境没有 pandas 依赖，但 RealStockDataFetcher 返回的是 DataFrame；尽量兼容
                df = fetcher.get_stock_data(code, days=250)
                if df is not None:
                    try:
                        # 尝试 DataFrame 转 records
                        if "日期" in df.columns:
                            # 若日期不是字符串，尝试格式化
                            try:
                                df["日期"] = df["日期"].dt.strftime("%Y-%m-%d")
                            except Exception:
                                df["日期"] = df["日期"].astype(str)
                        df = df.fillna(0)
                        bars = df.to_dict("records")
                    except Exception:
                        bars = []
            except Exception:
                bars = []
        if bars:
            insert_bars(conn, code, bars)
            latest = bars[0]["日期"]
            update_status(conn, code, latest, None)
        else:
            update_status(conn, code, None, "empty_bars")
    except Exception as e:
        update_status(conn, code, None, str(e))
    finally:
        if sleep_min > 0 or sleep_max > 0:
            time.sleep(random.uniform(sleep_min, max(sleep_min, sleep_max)))

def main():
    parser = argparse.ArgumentParser(description="构建市场数据库：股票列表 + 日K行情入库")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--start-date", default="2019-10-01")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--sleep-min", type=float, default=0.0)
    parser.add_argument("--sleep-max", type=float, default=0.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only-list", action="store_true")
    parser.add_argument("--progress-every", type=int, default=50)
    args = parser.parse_args()

    conn = connect_db(args.db_path)
    init_db(conn)

    # 股票列表获取（优先 Eastmoney，失败则回退本地 companies_metadata.json）
    stocks = fetch_stock_list_from_eastmoney()
    if not stocks:
        stocks = load_codes_from_metadata()
    if args.limit and args.limit > 0:
        stocks = stocks[:args.limit]

    upsert_stocks(conn, stocks)

    if args.only_list:
        print(json.dumps({
            "db_path": args.db_path,
            "start_date": args.start_date,
            "only_list": True,
            "stocks": len(stocks)
        }, ensure_ascii=False, indent=2))
        return

    items = [(s["code"], int(s.get("market_id") or (1 if s.get("market") == "SSE" else 0))) for s in stocks]
    results = {"processed": 0, "succeeded": 0, "failed": 0}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futs = []
        for code, market_id in items:
            futs.append(executor.submit(process_code, args.db_path, code, market_id, args.start_date, args.retries, args.sleep_min, args.sleep_max))
        for fut in concurrent.futures.as_completed(futs):
            results["processed"] += 1
            if args.progress_every and args.progress_every > 0 and results["processed"] % args.progress_every == 0:
                print(json.dumps({
                    "progress": {
                        "processed": results["processed"],
                        "total": len(items)
                    }
                }, ensure_ascii=False))

    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) FROM fetch_status WHERE error IS NULL AND last_success_date IS NOT NULL;")
    results["succeeded"] = int(cur.fetchone()[0] or 0)
    cur.execute("SELECT COUNT(1) FROM fetch_status WHERE error IS NOT NULL;")
    results["failed"] = int(cur.fetchone()[0] or 0)

    print(json.dumps({
        "db_path": args.db_path,
        "start_date": args.start_date,
        "summary": results
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
