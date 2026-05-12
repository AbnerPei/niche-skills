#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Export StockMaster daily_bars into Hive-style yearly Parquet partitions."""

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

import duckdb


SKILLS_ROOT = Path(os.environ.get("STOCKMASTER_NICHE_SKILLS_HOME", Path(__file__).resolve().parents[2]))
PROJECT_DIR = Path(os.environ.get("STOCKMASTER_ROOT", SKILLS_ROOT.parent / "StockMaster"))
DATACENTER_DIR = Path(os.environ.get("STOCKMASTER_DATA_CENTER", PROJECT_DIR / "DataCenter"))
DEFAULT_DB_PATH = DATACENTER_DIR / "market.sqlite"
DEFAULT_LAKE_DIR = DATACENTER_DIR / "MarketLake" / "daily_bars"


def iso_now() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).isoformat(timespec="seconds")


def sqlite_years(db_path: Path) -> List[int]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT CAST(substr(date, 1, 4) AS INTEGER) FROM daily_bars ORDER BY 1;"
        ).fetchall()
        return [int(row[0]) for row in rows if row[0] is not None]
    finally:
        conn.close()


def archive_map(data_center: Path) -> Dict[int, Path]:
    archive_dir = data_center / "Archives" / "sqlite"
    result: Dict[int, Path] = {}
    if not archive_dir.exists():
        return result
    for path in archive_dir.glob("market_*.sqlite"):
        try:
            year = int(path.stem.replace("market_", ""))
        except ValueError:
            continue
        result[year] = path
    return result


def source_years(hot_db: Path, data_center: Path) -> List[Tuple[int, Path]]:
    sources: Dict[int, Path] = {}
    for year in sqlite_years(hot_db):
        sources[year] = hot_db
    for year, path in archive_map(data_center).items():
        sources[year] = path
    return sorted(sources.items())


def export_year(con: duckdb.DuckDBPyConnection, year: int, source_path: Path, lake_dir: Path) -> Dict[str, object]:
    target_dir = lake_dir / f"year={year}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "data.parquet"
    tmp_path = target_dir / "data.parquet.tmp"
    if tmp_path.exists():
        tmp_path.unlink()
    source_sql = str(source_path).replace("'", "''")
    target_sql = str(tmp_path).replace("'", "''")
    year_text = str(year)
    con.execute(
        f"""
        COPY (
            SELECT
                code,
                date,
                open,
                close,
                high,
                low,
                volume,
                amount,
                amplitude,
                change_percent,
                change_amount,
                turnover_rate,
                {year}::INTEGER AS year
            FROM sqlite_scan('{source_sql}', 'daily_bars')
            WHERE substr(date, 1, 4) = '{year_text}'
        )
        TO '{target_sql}'
        (FORMAT PARQUET, COMPRESSION ZSTD);
        """
    )
    if target_path.exists():
        target_path.unlink()
    tmp_path.replace(target_path)
    parquet_sql = str(target_path).replace("'", "''")
    rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{parquet_sql}')").fetchone()[0]
    return {
        "year": year,
        "rows": int(rows),
        "source": str(source_path),
        "path": str(target_path),
        "size": target_path.stat().st_size,
    }


def write_manifest(data_center: Path, exported: List[Dict[str, object]]) -> Path:
    path = data_center / "MarketLake" / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": "V1.0.0",
                "format": "parquet",
                "partitioning": "hive/year",
                "updated_at": iso_now(),
                "daily_bars": exported,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export StockMaster daily bars to yearly Parquet partitions.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--data-center", default=str(DATACENTER_DIR))
    parser.add_argument("--lake-dir", default=str(DEFAULT_LAKE_DIR))
    args = parser.parse_args()

    db_path = Path(args.db_path).expanduser().resolve()
    data_center = Path(args.data_center).expanduser().resolve()
    lake_dir = Path(args.lake_dir).expanduser().resolve()
    years = source_years(db_path, data_center)
    if not years:
        raise RuntimeError("no daily_bars years found")

    con = duckdb.connect()
    con.execute("LOAD sqlite")
    exported = [export_year(con, year, source, lake_dir) for year, source in years]
    con.close()
    manifest_path = write_manifest(data_center, exported)
    print(json.dumps({"manifest": str(manifest_path), "exported": exported}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
