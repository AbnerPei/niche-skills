#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
import time
import random
import concurrent.futures
import importlib.util

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
SKILLS_ROOT = os.path.abspath(os.path.join(SKILL_ROOT, ".."))
PROJECT_DIR = os.environ.get("STOCKMASTER_ROOT", os.path.abspath(os.path.join(SKILLS_ROOT, "..", "StockMaster")))
ROOT_DIR = os.path.join(PROJECT_DIR, "StockMaster")
COMPANY_META_PATH = os.path.join(ROOT_DIR, "DataCenter", "companies_metadata.json")
DEFAULT_OUTPUT_DIR = os.path.join(ROOT_DIR, "DataCenter", "StockData", "AllStocks")
FETCH_SINGLE_PATH = os.path.join(BASE_DIR, "fetch_single_stock.py")

def load_fetch_single_module():
    spec = importlib.util.spec_from_file_location("fetch_single_stock", FETCH_SINGLE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def load_codes(codes_file=None):
    path = codes_file or COMPANY_META_PATH
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data.keys())

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()

def format_date(d):
    return d.strftime("%Y-%m-%d")

def validate_kline_list(items):
    if not isinstance(items, list) or not items:
        return False
    seen = set()
    for it in items:
        if not isinstance(it, dict):
            return False
        req = ["日期", "开盘价", "收盘价", "最高价", "最低价"]
        for k in req:
            if k not in it:
                return False
        try:
            _ = parse_date(it["日期"])
            float(it["开盘价"]); float(it["收盘价"]); float(it["最高价"]); float(it["最低价"])
        except Exception:
            return False
        if it["日期"] in seen:
            return False
        seen.add(it["日期"])
    return True

def merge_kline(existing, new_items):
    if not existing:
        return sorted(new_items, key=lambda x: x["日期"], reverse=True)
    merged = {it["日期"]: it for it in existing}
    for it in new_items:
        merged[it["日期"]] = it
    arr = list(merged.values())
    arr.sort(key=lambda x: x["日期"], reverse=True)
    return arr

def compute_mas_desc(records, periods):
    if not records:
        return records
    asc = list(reversed(records))
    closes = [float(x.get("收盘价", 0)) for x in asc]
    sums = [0.0]
    for v in closes:
        sums.append(sums[-1] + v)
    def window_avg(i, p):
        if i + 1 < p:
            return None
        s = sums[i + 1] - sums[i + 1 - p]
        return s / p
    for idx, item in enumerate(asc):
        for p in periods:
            val = window_avg(idx, p)
            if val is not None:
                item[f"MA{p}"] = round(val, 6)
    return list(reversed(asc))

def count_gaps_ignore_weekend(records):
    if not records:
        return 0, None, None
    dates = sorted([parse_date(x["日期"]) for x in records])
    start = dates[0]
    end = dates[-1]
    have = set(dates)
    gaps = 0
    cur = start
    while cur <= end:
        if cur.weekday() < 5 and cur not in have:
            gaps += 1
        cur += timedelta(days=1)
    return gaps, start, end

def latest_date_in_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "kline" in data and isinstance(data["kline"], list) and data["kline"]:
            return data["kline"][0]["日期"]
    except Exception:
        return None
    return None

def save_stock(path, code, kline, info=None):
    payload = {
        "code": code,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kline": kline
    }
    if info:
        payload["info"] = info
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def fetch_with_retry(fetcher_func, code, start_date, retries, backoff_min, backoff_max):
    attempt = 0
    while True:
        try:
            return fetcher_func(code, start_date)
        except Exception:
            attempt += 1
            if attempt > retries:
                raise
            time.sleep(random.uniform(backoff_min, backoff_max) * attempt)

def make_fetcher(module):
    def _fetch(code, start_date):
        kline = module.fetch_kline_eastmoney(code, start_date=start_date)
        if not kline:
            kline = []
        return kline
    return _fetch

def make_snapshot_bar(snapshot):
    if not snapshot:
        return None
    snapshot_date = snapshot.get("date")
    if not snapshot_date:
        return None
    try:
        parse_date(snapshot_date)
    except Exception:
        return None
    return {
        "日期": snapshot_date,
        "开盘价": snapshot.get("open", 0),
        "收盘价": snapshot.get("price", 0),
        "最高价": snapshot.get("high", 0),
        "最低价": snapshot.get("low", 0),
        "成交量": snapshot.get("volume", 0),
        "成交额": snapshot.get("amount", 0),
        "涨跌幅": snapshot.get("change_percent", 0),
        "涨跌额": snapshot.get("change_amount", 0),
        "换手率": snapshot.get("turnover_rate", 0)
    }

def ensure_latest_snapshot(module, code, existing, new_items):
    try:
        snapshot = module.fetch_snapshot(code)
    except Exception:
        snapshot = None
    snapshot_bar = make_snapshot_bar(snapshot)
    if not snapshot_bar:
        return new_items, snapshot

    latest_existing = existing[0]["日期"] if existing else None
    latest_new = new_items[0]["日期"] if new_items else None
    latest_known = max([d for d in [latest_existing, latest_new] if d], default=None)
    if latest_known and snapshot_bar["日期"] <= latest_known:
        return new_items, snapshot

    return [snapshot_bar] + new_items, snapshot

def process_code(code, args, module):
    ensure_dir(args.output_dir)
    out_path = os.path.join(args.output_dir, f"{code}.json")
    start_date = args.start_date
    if os.path.exists(out_path):
        latest = latest_date_in_file(out_path)
        if latest:
            try:
                d = parse_date(latest) + timedelta(days=1)
                if d > parse_date(start_date):
                    start_date = format_date(d)
            except Exception:
                pass
    existing = []
    existing_info = None
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, dict) and "kline" in obj and isinstance(obj["kline"], list):
                existing = obj["kline"]
                existing_info = obj.get("info")
        except Exception:
            existing = []
            existing_info = None

    fetcher = make_fetcher(module)
    kline_new = fetch_with_retry(fetcher, code, start_date, args.retries, args.backoff_min, args.backoff_max)
    if args.sleep_min > 0 or args.sleep_max > 0:
        time.sleep(random.uniform(args.sleep_min, max(args.sleep_min, args.sleep_max)))
    if not validate_kline_list(kline_new) and kline_new:
        raise RuntimeError(f"Invalid kline for {code}")

    kline_new, snapshot = ensure_latest_snapshot(module, code, existing, kline_new)
    if not validate_kline_list(kline_new) and kline_new:
        raise RuntimeError(f"Invalid latest snapshot merge for {code}")

    merged = merge_kline(existing, kline_new)
    if args.compute_ma:
        merged = compute_mas_desc(merged, [5,10,20,30,60])
    if not validate_kline_list(merged):
        raise RuntimeError(f"Validation failed after merge for {code}")
    save_stock(out_path, code, merged, info=snapshot or existing_info)
    gaps, start_d, end_d = count_gaps_ignore_weekend(merged)
    earliest = format_date(start_d) if start_d else None
    latest = format_date(end_d) if end_d else None
    return {"code": code, "count_added": len(kline_new), "total": len(merged), "gaps": gaps, "earliest": earliest, "latest": latest}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default="2019-10-01")
    parser.add_argument("--codes-file", default=None)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--backoff-min", type=float, default=0.5)
    parser.add_argument("--backoff-max", type=float, default=1.5)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--compute-ma", action="store_true")
    parser.add_argument("--sleep-min", type=float, default=0.0)
    parser.add_argument("--sleep-max", type=float, default=0.0)
    parser.add_argument("--status-file", default=None)
    args = parser.parse_args()
    module = load_fetch_single_module()
    codes = load_codes(args.codes_file)
    if args.limit and args.limit > 0:
        codes = codes[:args.limit]
    results = []
    errors = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        fut_map = {executor.submit(process_code, code, args, module): code for code in codes}
        for fut in concurrent.futures.as_completed(fut_map):
            code = fut_map[fut]
            try:
                res = fut.result()
                results.append(res)
            except Exception as e:
                errors.append({"code": code, "error": str(e)})
    earliest_all = None
    latest_all = None
    if results:
        try:
            earliest_all = min([r["earliest"] for r in results if r.get("earliest")])
            latest_all = max([r["latest"] for r in results if r.get("latest")])
        except Exception:
            pass
    summary = {
        "success": len(errors) == 0,
        "start_date": args.start_date,
        "output_dir": args.output_dir,
        "processed": len(codes),
        "succeeded": len(results),
        "failed": len(errors),
        "errors": errors,
        "stats": {
            "added_total": sum(r["count_added"] for r in results) if results else 0,
            "gap_total": sum(r.get("gaps", 0) for r in results) if results else 0,
            "earliest_overall": earliest_all,
            "latest_overall": latest_all
        }
    }
    if args.status_file:
        try:
            with open(args.status_file, "w", encoding="utf-8") as f:
                json.dump({"results": results, "summary": summary}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
