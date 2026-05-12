#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Archive StockMaster market.sqlite into hot SQLite + yearly cold SQLite files.

The script is intentionally conservative:
- it creates a timestamped full backup before any destructive change;
- it writes archive files through .tmp files and validates them before replace;
- it only trims the hot database when --execute is passed.
"""

import argparse
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


SKILLS_ROOT = Path(os.environ.get("STOCKMASTER_NICHE_SKILLS_HOME", Path(__file__).resolve().parents[2]))
PROJECT_DIR = Path(os.environ.get("STOCKMASTER_ROOT", SKILLS_ROOT.parent / "StockMaster"))
DATACENTER_DIR = Path(os.environ.get("STOCKMASTER_DATA_CENTER", PROJECT_DIR / "DataCenter"))
DEFAULT_DB_PATH = DATACENTER_DIR / "market.sqlite"


def now_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def iso_now() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).isoformat(timespec="seconds")


def connect(path: Path, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        uri = f"file:{path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def scalar(conn: sqlite3.Connection, sql: str, params: Iterable = ()) -> object:
    row = conn.execute(sql, tuple(params)).fetchone()
    return None if row is None else row[0]


def required_table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return scalar(
        conn,
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1;",
        (table,),
    ) == 1


def validate_source(conn: sqlite3.Connection) -> None:
    missing = [table for table in ("stocks", "daily_bars") if not required_table_exists(conn, table)]
    if missing:
        raise RuntimeError(f"market.sqlite missing required tables: {', '.join(missing)}")
    result = scalar(conn, "PRAGMA integrity_check;")
    if result != "ok":
        raise RuntimeError(f"source integrity_check failed: {result}")


def checkpoint_sqlite(db_path: Path) -> None:
    conn = connect(db_path)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        conn.execute("PRAGMA journal_mode=DELETE;")
    finally:
        conn.close()


def backup_database(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"market.sqlite.before_archive_{now_slug()}.sqlite"
    checkpoint_sqlite(db_path)
    shutil.copy2(db_path, backup_path)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(db_path) + suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, Path(str(backup_path) + suffix))
    return backup_path


def fetch_year_stats(conn: sqlite3.Connection) -> List[Dict[str, object]]:
    rows = conn.execute(
        """
        SELECT substr(date, 1, 4) AS year,
               COUNT(*) AS rows,
               COUNT(DISTINCT code) AS stocks,
               MIN(date) AS min_date,
               MAX(date) AS max_date
        FROM daily_bars
        GROUP BY year
        ORDER BY year;
        """
    ).fetchall()
    return [
        {
            "year": int(row["year"]),
            "rows": int(row["rows"]),
            "stocks": int(row["stocks"]),
            "min_date": row["min_date"],
            "max_date": row["max_date"],
        }
        for row in rows
        if row["year"]
    ]


def table_sql(conn: sqlite3.Connection, table: str) -> str:
    sql = scalar(conn, "SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", (table,))
    if not sql:
        raise RuntimeError(f"cannot read table schema: {table}")
    return str(sql)


def archive_schema(source: sqlite3.Connection, target: sqlite3.Connection) -> None:
    target.execute(table_sql(source, "stocks"))
    target.execute(table_sql(source, "daily_bars"))
    target.execute(
        """
        CREATE TABLE archive_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    target.execute("CREATE INDEX IF NOT EXISTS idx_bars_date ON daily_bars(date);")


def copy_year_to_archive(source_path: Path, archive_path: Path, year: int) -> Dict[str, object]:
    tmp_path = archive_path.with_suffix(".sqlite.tmp")
    bak_path = archive_path.with_suffix(".sqlite.bak")
    for path in (tmp_path,):
        if path.exists():
            path.unlink()

    source = connect(source_path, readonly=True)
    target = connect(tmp_path)
    try:
        archive_schema(source, target)
        source_sql = str(source_path).replace("'", "''")
        target.execute(f"ATTACH DATABASE '{source_sql}' AS source_db;")
        target.execute("INSERT INTO stocks SELECT * FROM source_db.stocks;")
        target.execute(
            """
            INSERT INTO daily_bars
            SELECT * FROM source_db.daily_bars
            WHERE substr(date, 1, 4) = ?;
            """,
            (str(year),),
        )
        stats = target.execute(
            """
            SELECT COUNT(*) AS rows,
                   COUNT(DISTINCT code) AS stocks,
                   MIN(date) AS min_date,
                   MAX(date) AS max_date
            FROM daily_bars;
            """
        ).fetchone()
        meta = {
            "version": "V1.0.0",
            "year": str(year),
            "rows": str(int(stats["rows"] or 0)),
            "stocks": str(int(stats["stocks"] or 0)),
            "min_date": stats["min_date"] or "",
            "max_date": stats["max_date"] or "",
            "created_at": iso_now(),
        }
        target.executemany(
            "INSERT INTO archive_meta(key, value) VALUES(?, ?);",
            sorted(meta.items()),
        )
        target.commit()
        target.execute("DETACH DATABASE source_db;")
        integrity = scalar(target, "PRAGMA integrity_check;")
        if integrity != "ok":
            raise RuntimeError(f"archive integrity_check failed for {year}: {integrity}")
    finally:
        target.close()
        source.close()

    verify_source = connect(source_path, readonly=True)
    verify_target = sqlite3.connect(tmp_path)
    try:
        expected_rows = int(
            scalar(
                verify_source,
                "SELECT COUNT(*) FROM daily_bars WHERE substr(date, 1, 4)=?;",
                (str(year),),
            ) or 0
        )
        actual_rows = int(verify_target.execute("SELECT COUNT(*) FROM daily_bars;").fetchone()[0])
    finally:
        verify_target.close()
        verify_source.close()
    if expected_rows != actual_rows:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(f"archive row mismatch for {year}: expected={expected_rows}, actual={actual_rows}")

    if archive_path.exists():
        if bak_path.exists():
            bak_path.unlink()
        archive_path.replace(bak_path)
    tmp_path.replace(archive_path)
    if bak_path.exists():
        bak_path.unlink()

    return {
        "year": year,
        "rows": actual_rows,
        "path": str(archive_path),
    }


def write_manifest(data_center: Path, latest_year: int, hot_years: List[int], archive_years: List[int]) -> Path:
    manifest = {
        "version": "V1.0.0",
        "latest_year": latest_year,
        "hot_years": hot_years,
        "archive_years": archive_years,
        "sqlite_schema_version": 1,
        "duckdb_cache_version": 1,
        "updated_at": iso_now(),
    }
    path = data_center / "database_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def optimize_hot_db(conn: sqlite3.Connection, hot_start_year: int, drop_code_index: bool) -> None:
    cutoff = f"{hot_start_year:04d}-01-01"
    conn.execute("DELETE FROM daily_bars WHERE date < ?;", (cutoff,))
    if drop_code_index:
        conn.execute("DROP INDEX IF EXISTS idx_bars_code;")
    conn.commit()
    conn.execute("VACUUM;")
    conn.execute("PRAGMA optimize;")


def format_size(path: Path) -> str:
    if not path.exists():
        return "0 B"
    size = path.stat().st_size
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024
    return f"{size:.1f} GB"


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive StockMaster market.sqlite by year.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--data-center", default=str(DATACENTER_DIR))
    parser.add_argument("--hot-years", type=int, default=3)
    parser.add_argument("--execute", action="store_true", help="Actually trim hot database after archive validation.")
    parser.add_argument("--no-drop-code-index", action="store_true", help="Keep idx_bars_code in the hot database.")
    parser.add_argument("--backup-dir", default=None)
    args = parser.parse_args()

    db_path = Path(args.db_path).expanduser().resolve()
    data_center = Path(args.data_center).expanduser().resolve()
    archive_dir = data_center / "Archives" / "sqlite"
    backup_dir = Path(args.backup_dir).expanduser().resolve() if args.backup_dir else data_center / "Backups"

    source = connect(db_path)
    try:
        validate_source(source)
        latest_date = scalar(source, "SELECT MAX(date) FROM daily_bars;")
        if not latest_date:
            raise RuntimeError("daily_bars is empty")
        latest_year = int(str(latest_date)[:4])
        hot_start_year = latest_year - max(1, args.hot_years) + 1
        stats = fetch_year_stats(source)
        archive_years = [row["year"] for row in stats if int(row["year"]) < hot_start_year]
        hot_years = [year for year in range(hot_start_year, latest_year + 1)]
    finally:
        source.close()

    print(json.dumps({
        "db_path": str(db_path),
        "before_size": format_size(db_path),
        "latest_year": latest_year,
        "hot_years": hot_years,
        "archive_years": archive_years,
        "execute": args.execute,
    }, ensure_ascii=False, indent=2))

    if not archive_years:
        manifest_path = write_manifest(data_center, latest_year, hot_years, [])
        print(f"No archive years found. Manifest updated: {manifest_path}")
        return 0

    backup_path = backup_database(db_path, backup_dir) if args.execute else None
    if backup_path:
        print(f"Backup created: {backup_path} ({format_size(backup_path)})")

    archived = []
    for year in archive_years:
        archive_path = archive_dir / f"market_{year}.sqlite"
        archived.append(copy_year_to_archive(db_path, archive_path, year))
        print(f"Archived {year}: {archive_path} ({format_size(archive_path)})")

    if args.execute:
        conn = connect(db_path)
        try:
            optimize_hot_db(conn, hot_start_year, drop_code_index=not args.no_drop_code_index)
        finally:
            conn.close()
        print(f"Hot database optimized: {db_path} ({format_size(db_path)})")
    else:
        print("Dry run complete: archives were generated, hot database was not trimmed. Pass --execute to trim it.")

    manifest_path = write_manifest(data_center, latest_year, hot_years, archive_years)
    print(f"Manifest updated: {manifest_path}")
    print(json.dumps({"archived": archived}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
