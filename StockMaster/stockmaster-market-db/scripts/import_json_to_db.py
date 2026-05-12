#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import argparse
import sqlite3
import csv
from datetime import datetime
from typing import Dict, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
SKILLS_ROOT = os.path.abspath(os.path.join(SKILL_ROOT, ".."))
PROJECT_DIR = os.environ.get("STOCKMASTER_ROOT", os.path.abspath(os.path.join(SKILLS_ROOT, "..", "StockMaster")))
ROOT_DIR = os.path.join(PROJECT_DIR, "StockMaster")
DATACENTER_DIR = os.path.join(ROOT_DIR, "DataCenter")
DEFAULT_DB_PATH = os.path.join(DATACENTER_DIR, "market.sqlite")
STOCKDATA_DIR = os.path.join(DATACENTER_DIR, "StockData")
STOCKLIST_DIR = os.path.join(DATACENTER_DIR, "StockList")

def now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def connect_db(db_path: str):
    if not os.path.exists(os.path.dirname(db_path)):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def ensure_tables(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS stocks (
        code TEXT PRIMARY KEY,
        name TEXT,
        market TEXT,
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
    conn.commit()

def normalize_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    value = str(name).strip()
    return value or None

def load_stock_names(stocklist_dir: str) -> Dict[str, str]:
    names: Dict[str, str] = {}
    if not os.path.isdir(stocklist_dir):
        return names
    for filename in ("szse_stocks.csv", "sse_stocks.csv", "bse_stocks.csv"):
        path = os.path.join(stocklist_dir, filename)
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = str(
                        row.get("股票代码")
                        or row.get("code")
                        or row.get("证券代码")
                        or ""
                    ).strip()
                    name = normalize_name(
                        row.get("股票名称")
                        or row.get("name")
                        or row.get("证券简称")
                    )
                    if code and name and code not in names:
                        names[code] = name
        except Exception:
            continue
    return names

def insert_stock(conn: sqlite3.Connection, code: str, info: dict, stock_names: Dict[str, str]):
    name = normalize_name(info.get("name")) or stock_names.get(code)
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO stocks(code,name,market,board,is_st,industry,area,listed_at,status,updated_at)
    VALUES(?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(code) DO UPDATE SET
        name=COALESCE(NULLIF(excluded.name, ''), NULLIF(stocks.name, ''), stocks.code),
        updated_at=excluded.updated_at;
    """, (
        code,
        name,
        None, None, 0,
        None, None, None,
        "active",
        now_ts()
    ))
    conn.commit()

def insert_bars(conn: sqlite3.Connection, code: str, bars: list):
    cur = conn.cursor()
    for b in bars:
        cur.execute("""
        INSERT OR REPLACE INTO daily_bars
        (code,date,open,close,high,low,volume,amount,amplitude,change_percent,change_amount,turnover_rate)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
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
    conn.commit()

def filter_bars_by_start_date(bars: list, start_date: str) -> list:
    if not bars:
        return []
    return [b for b in bars if isinstance(b, dict) and (b.get("日期") or "") >= start_date]

def delete_bars_before(conn: sqlite3.Connection, start_date: str):
    cur = conn.cursor()
    cur.execute("DELETE FROM daily_bars WHERE date < ?;", (start_date,))
    conn.commit()

def iter_json_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn.endswith(".json"):
                yield os.path.join(dirpath, fn)

def resolve_code(obj: dict, path: str) -> str | None:
    info = obj.get("info") or {}
    code = info.get("code") or obj.get("code")
    if code:
        return str(code)
    stem = os.path.splitext(os.path.basename(path))[0]
    return stem or None

def main():
    parser = argparse.ArgumentParser(description="导入 DataCenter/StockData 下的 JSON K线数据到 SQLite")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--stockdata-dir", default=STOCKDATA_DIR)
    parser.add_argument("--start-date", default="2019-10-01")
    parser.add_argument("--purge-before-start", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    conn = connect_db(args.db_path)
    ensure_tables(conn)
    stock_names = load_stock_names(
        os.path.join(os.path.dirname(args.stockdata_dir), "StockList")
    )
    if args.purge_before_start:
        delete_bars_before(conn, args.start_date)

    files = list(iter_json_files(args.stockdata_dir))
    if args.limit and args.limit > 0:
        files = files[:args.limit]

    imported = 0
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            info = obj.get("info") or {}
            code = resolve_code(obj, path)
            bars = filter_bars_by_start_date(obj.get("kline") or [], args.start_date)
            if not code or not bars:
                continue
            insert_stock(conn, code, info, stock_names)
            insert_bars(conn, code, bars)
            imported += 1
        except Exception:
            pass

    print(json.dumps({
        "db_path": args.db_path,
        "stockdata_dir": args.stockdata_dir,
        "start_date": args.start_date,
        "purge_before_start": args.purge_before_start,
        "files_scanned": len(files),
        "imported": imported
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
