#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Publish, restore, and verify StockMaster database snapshots on Aliyun OSS.

The script keeps OSS as a distribution layer only. Restored databases always
land under STOCKMASTER_DATA_CENTER so the app can continue using its normal
FileManager database helpers.
"""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional


SKILLS_ROOT = Path(os.environ.get("STOCKMASTER_NICHE_SKILLS_HOME", Path(__file__).resolve().parents[2]))
PROJECT_DIR = Path(os.environ.get("STOCKMASTER_ROOT", SKILLS_ROOT.parent / "StockMaster"))
DATACENTER_DIR = Path(os.environ.get("STOCKMASTER_DATA_CENTER", PROJECT_DIR / "DataCenter"))
DEFAULT_PREFIX = "stockmaster"
RUNTIME_CACHE_EXCLUDED_FILE_NAMES = {"ossutilconfig", "ossutil-wrapper.sh"}


def iso_now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def now_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def data_center_path(relative: str) -> Path:
    return DATACENTER_DIR / relative


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def connect_sqlite(path: Path, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def scalar(conn: sqlite3.Connection, sql: str, params: Iterable = ()) -> object:
    row = conn.execute(sql, tuple(params)).fetchone()
    return None if row is None else row[0]


def validate_market_sqlite(path: Path) -> Dict[str, object]:
    if not path.exists():
        raise RuntimeError(f"market.sqlite not found: {path}")
    conn = connect_sqlite(path, readonly=True)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('stocks', 'daily_bars');"
            )
        }
        missing = sorted({"stocks", "daily_bars"} - tables)
        if missing:
            raise RuntimeError(f"market.sqlite missing required tables: {', '.join(missing)}")
        integrity = scalar(conn, "PRAGMA integrity_check;")
        if integrity != "ok":
            raise RuntimeError(f"market.sqlite integrity_check failed: {integrity}")
        return {
            "trade_date": scalar(conn, "SELECT MAX(date) FROM daily_bars;") or "",
            "min_date": scalar(conn, "SELECT MIN(date) FROM daily_bars;") or "",
            "daily_bars": int(scalar(conn, "SELECT COUNT(*) FROM daily_bars;") or 0),
            "stocks": int(scalar(conn, "SELECT COUNT(*) FROM stocks;") or 0),
        }
    finally:
        conn.close()


def checkpoint_market_sqlite(path: Path) -> None:
    conn = connect_sqlite(path)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        conn.execute("PRAGMA journal_mode=DELETE;")
    finally:
        conn.close()


def read_database_manifest() -> Dict[str, object]:
    path = DATACENTER_DIR / "database_manifest.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def zip_file(source: Path, target: Path, arcname: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.write(source, arcname)


def zip_directory(
    source: Path,
    target: Path,
    base: Path,
    excluded_file_names: Optional[Iterable[str]] = None,
) -> bool:
    if not source.exists():
        return False
    excluded = set(excluded_file_names or [])
    files = [
        path for path in source.rglob("*")
        if path.is_file() and path.name not in excluded
    ]
    if not files:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in files:
            zf.write(path, path.relative_to(base))
    return True


def try_checkpoint_sqlite(path: Path) -> None:
    if not path.exists():
        return
    try:
        conn = sqlite3.connect(path)
        try:
            conn.execute("PRAGMA busy_timeout=2000;")
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        finally:
            conn.close()
    except sqlite3.Error:
        return


def build_file_entry(role: str, path: Path, object_key: str, target: str, optional: bool = False) -> Dict[str, object]:
    entry: Dict[str, object] = {
        "role": role,
        "path": object_key,
        "target": target,
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if optional:
        entry["optional"] = True
    return entry


def append_directory_package(
    package_entries: List[Dict[str, object]],
    *,
    enabled: bool,
    role: str,
    source_relative: str,
    object_name: str,
    target: str,
    workdir: Path,
    optional: bool = True,
    excluded_file_names: Optional[Iterable[str]] = None,
) -> None:
    if not enabled:
        return
    zip_path = workdir / object_name
    if zip_directory(
        data_center_path(source_relative),
        zip_path,
        DATACENTER_DIR,
        excluded_file_names=excluded_file_names,
    ):
        package_entries.append(
            {
                "role": role,
                "path": zip_path,
                "object_name": object_name,
                "target": target,
                "optional": optional,
            }
        )


def append_file_package(
    package_entries: List[Dict[str, object]],
    *,
    enabled: bool,
    role: str,
    source_relative: str,
    object_name: str,
    target: str,
    workdir: Path,
    optional: bool = True,
) -> None:
    if not enabled:
        return
    source = data_center_path(source_relative)
    if not source.exists():
        return
    zip_path = workdir / object_name
    zip_file(source, zip_path, source_relative)
    package_entries.append(
        {
            "role": role,
            "path": zip_path,
            "object_name": object_name,
            "target": target,
            "optional": optional,
        }
    )


def make_manifest(
    version: str,
    prefix: str,
    snapshot_dir: str,
    sqlite_stats: Dict[str, object],
    package_entries: List[Dict[str, object]],
) -> Dict[str, object]:
    database_manifest = read_database_manifest()
    files = []
    for entry in package_entries:
        object_name = entry["object_name"]
        files.append(
            build_file_entry(
                role=entry["role"],
                path=entry["path"],
                object_key=f"{prefix}/snapshots/{snapshot_dir}/{object_name}",
                target=entry["target"],
                optional=bool(entry.get("optional", False)),
            )
        )
    return {
        "version": version,
        "trade_date": sqlite_stats.get("trade_date", ""),
        "schema_version": database_manifest.get("sqlite_schema_version", 1),
        "hot_years": database_manifest.get("hot_years", []),
        "archive_years": database_manifest.get("archive_years", []),
        "created_at": iso_now(),
        "stats": sqlite_stats,
        "files": files,
    }


def require_ossutil(explicit: Optional[str] = None) -> str:
    candidates = [explicit] if explicit else []
    candidates.extend(["ossutil", "ossutil64"])
    for candidate in candidates:
        if candidate and shutil.which(candidate):
            return candidate
    raise RuntimeError("ossutil not found. Install ossutil or set --ossutil / PATH first.")


def run_ossutil_cp(
    source: str,
    destination: str,
    ossutil: Optional[str] = None,
    config_file: Optional[str] = None,
) -> None:
    command = [require_ossutil(ossutil), "cp", source, destination, "-f"]
    if config_file:
        command.extend(["--config-file", config_file])
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"ossutil cp failed: {detail}")


def run_ossutil_rm(
    target: str,
    ossutil: Optional[str] = None,
    config_file: Optional[str] = None,
) -> None:
    command = [require_ossutil(ossutil), "rm", target, "-r", "-f"]
    if config_file:
        command.extend(["--config-file", config_file])
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"ossutil rm failed: {detail}")


def object_url(public_base_url: str, object_key: str) -> str:
    return public_base_url.rstrip("/") + "/" + object_key.lstrip("/")


def download_object(object_key: str, target: Path, args: argparse.Namespace) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if args.public_base_url:
        urllib.request.urlretrieve(object_url(args.public_base_url, object_key), target)
        return
    bucket = args.bucket or os.environ.get("ALIYUN_OSS_BUCKET")
    if not bucket:
        raise RuntimeError("Missing OSS bucket. Set ALIYUN_OSS_BUCKET or pass --bucket.")
    run_ossutil_cp(f"oss://{bucket}/{object_key}", str(target), args.ossutil, args.oss_config_file)


def upload_file(path: Path, object_key: str, args: argparse.Namespace) -> None:
    bucket = args.bucket or os.environ.get("ALIYUN_OSS_BUCKET")
    if not bucket:
        raise RuntimeError("Missing OSS bucket. Set ALIYUN_OSS_BUCKET or pass --bucket.")
    run_ossutil_cp(str(path), f"oss://{bucket}/{object_key}", args.ossutil, args.oss_config_file)


def cleanup_staging_prefix(prefix: str, args: argparse.Namespace) -> Optional[str]:
    bucket = args.bucket or os.environ.get("ALIYUN_OSS_BUCKET")
    if not bucket:
        raise RuntimeError("Missing OSS bucket. Set ALIYUN_OSS_BUCKET or pass --bucket.")
    staging_prefix = f"oss://{bucket}/{prefix}/snapshots/.staging/"
    try:
        run_ossutil_rm(staging_prefix, args.ossutil, args.oss_config_file)
        return None
    except RuntimeError as exc:
        return str(exc)


def prepare_packages(args: argparse.Namespace, workdir: Path) -> Dict[str, object]:
    market_sqlite = data_center_path("market.sqlite")
    checkpoint_market_sqlite(market_sqlite)
    sqlite_stats = validate_market_sqlite(market_sqlite)

    market_zip = workdir / "market.sqlite.zip"
    zip_file(market_sqlite, market_zip, "market.sqlite")
    package_entries: List[Dict[str, object]] = [
        {
            "role": "market_hot",
            "path": market_zip,
            "object_name": "market.sqlite.zip",
            "target": "DataCenter/market.sqlite",
        }
    ]

    archives_zip = workdir / "archives.sqlite.zip"
    if (args.include_archives or args.include_runtime) and zip_directory(
        data_center_path("Archives/sqlite"),
        archives_zip,
        DATACENTER_DIR,
    ):
        package_entries.append(
            {
                "role": "market_archives",
                "path": archives_zip,
                "object_name": "archives.sqlite.zip",
                "target": "DataCenter/Archives/sqlite/",
            }
        )

    lake_zip = workdir / "market_lake.zip"
    if (args.include_lake or args.include_runtime) and zip_directory(data_center_path("MarketLake"), lake_zip, DATACENTER_DIR):
        package_entries.append(
            {
                "role": "market_lake",
                "path": lake_zip,
                "object_name": "market_lake.zip",
                "target": "DataCenter/MarketLake/",
                "optional": True,
            }
        )

    try_checkpoint_sqlite(data_center_path("SwiftData/default.store"))
    append_directory_package(
        package_entries,
        enabled=args.include_cache or args.include_runtime,
        role="runtime_cache",
        source_relative="Cache",
        object_name="runtime_cache.zip",
        target="DataCenter/Cache/",
        workdir=workdir,
        excluded_file_names=RUNTIME_CACHE_EXCLUDED_FILE_NAMES,
    )
    append_directory_package(
        package_entries,
        enabled=args.include_swiftdata or args.include_runtime,
        role="runtime_swiftdata",
        source_relative="SwiftData",
        object_name="runtime_swiftdata.zip",
        target="DataCenter/SwiftData/",
        workdir=workdir,
    )
    append_file_package(
        package_entries,
        enabled=args.include_duckdb or args.include_runtime,
        role="market_duckdb",
        source_relative="market.duckdb",
        object_name="market.duckdb.zip",
        target="DataCenter/market.duckdb",
        workdir=workdir,
    )

    return {"sqlite_stats": sqlite_stats, "package_entries": package_entries}


def command_upload(args: argparse.Namespace) -> None:
    require_ossutil(args.ossutil)
    if not (args.bucket or os.environ.get("ALIYUN_OSS_BUCKET")):
        raise RuntimeError("Missing OSS bucket. Set ALIYUN_OSS_BUCKET or pass --bucket.")
    prefix = args.prefix.strip("/")
    version = args.version or datetime.now().strftime("%Y-%m-%d")
    with tempfile.TemporaryDirectory(prefix="stockmaster_oss_upload_") as tmp:
        workdir = Path(tmp)
        prepared = prepare_packages(args, workdir)
        package_entries = prepared["package_entries"]
        sqlite_stats = prepared["sqlite_stats"]

        run_id = now_slug()
        staging_dir = f".staging/{run_id}"
        staging_manifest = make_manifest(version, prefix, staging_dir, sqlite_stats, package_entries)
        staging_manifest_path = workdir / "manifest.staging.json"
        staging_manifest_path.write_text(json.dumps(staging_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        for entry in package_entries:
            upload_file(entry["path"], f"{prefix}/snapshots/{staging_dir}/{entry['object_name']}", args)
        upload_file(staging_manifest_path, f"{prefix}/snapshots/{staging_dir}/manifest.json", args)

        latest_manifest = make_manifest(version, prefix, "latest", sqlite_stats, package_entries)
        latest_manifest_path = workdir / "manifest.latest.json"
        latest_manifest_path.write_text(json.dumps(latest_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for entry in package_entries:
            upload_file(entry["path"], f"{prefix}/snapshots/latest/{entry['object_name']}", args)
        upload_file(latest_manifest_path, f"{prefix}/snapshots/latest/manifest.json", args)

        monthly_uploaded = False
        if args.publish_monthly:
            month = args.month or datetime.now().strftime("%Y-%m")
            monthly_manifest = make_manifest(version, prefix, f"monthly/{month}", sqlite_stats, package_entries)
            monthly_manifest_path = workdir / "manifest.monthly.json"
            monthly_manifest_path.write_text(
                json.dumps(monthly_manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            for entry in package_entries:
                upload_file(entry["path"], f"{prefix}/snapshots/monthly/{month}/{entry['object_name']}", args)
            upload_file(monthly_manifest_path, f"{prefix}/snapshots/monthly/{month}/manifest.json", args)
            monthly_uploaded = True

        cleanup_warning = cleanup_staging_prefix(prefix, args)

        print(json.dumps({
            "ok": True,
            "action": "upload",
            "version": version,
            "trade_date": sqlite_stats.get("trade_date", ""),
            "files": [entry["object_name"] for entry in package_entries],
            "staging": f"{prefix}/snapshots/{staging_dir}/",
            "latest": f"{prefix}/snapshots/latest/",
            "monthly_uploaded": monthly_uploaded,
            "staging_cleanup": "cleared" if cleanup_warning is None else "warning",
            "staging_cleanup_warning": cleanup_warning,
        }, ensure_ascii=False, indent=2))


def verify_zip(entry: Dict[str, object], zip_path: Path) -> None:
    expected_size = int(entry.get("size", -1))
    expected_sha = str(entry.get("sha256", ""))
    if expected_size >= 0 and zip_path.stat().st_size != expected_size:
        raise RuntimeError(f"{entry['role']} size mismatch")
    actual_sha = sha256_file(zip_path)
    if expected_sha and actual_sha != expected_sha:
        raise RuntimeError(f"{entry['role']} sha256 mismatch: expected={expected_sha}, actual={actual_sha}")


def safe_extract(zip_path: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            output = (target_dir / member.filename).resolve()
            if not str(output).startswith(str(target_dir.resolve()) + os.sep):
                raise RuntimeError(f"unsafe zip member: {member.filename}")
        zf.extractall(target_dir)


def backup_existing_market_sqlite() -> Optional[Path]:
    market_sqlite = data_center_path("market.sqlite")
    if not market_sqlite.exists():
        return None
    backup_dir = data_center_path("Backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"market.sqlite.before_oss_restore_{now_slug()}.sqlite"
    checkpoint_market_sqlite(market_sqlite)
    shutil.copy2(market_sqlite, backup_path)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(market_sqlite) + suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, Path(str(backup_path) + suffix))
    return backup_path


def command_download(args: argparse.Namespace) -> None:
    if not args.public_base_url:
        require_ossutil(args.ossutil)
        if not (args.bucket or os.environ.get("ALIYUN_OSS_BUCKET")):
            raise RuntimeError("Missing OSS bucket. Set ALIYUN_OSS_BUCKET or pass --bucket.")
    prefix = args.prefix.strip("/")
    manifest_key = f"{prefix}/snapshots/{args.snapshot}/manifest.json"
    DATACENTER_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="stockmaster_oss_restore_") as tmp:
        workdir = Path(tmp)
        manifest_path = workdir / "manifest.json"
        download_object(manifest_key, manifest_path, args)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        wanted_roles = {"market_hot"}
        if args.include_archives or args.include_runtime:
            wanted_roles.add("market_archives")
        if args.include_lake or args.include_runtime:
            wanted_roles.add("market_lake")
        if args.include_cache or args.include_runtime:
            wanted_roles.add("runtime_cache")
        if args.include_swiftdata or args.include_runtime:
            wanted_roles.add("runtime_swiftdata")
        if args.include_duckdb or args.include_runtime:
            wanted_roles.add("market_duckdb")

        downloaded_roles: List[str] = []
        restore_dir = workdir / "restore"
        for entry in manifest.get("files", []):
            role = entry.get("role")
            if role not in wanted_roles:
                continue
            zip_path = workdir / Path(str(entry["path"])).name
            download_object(str(entry["path"]), zip_path, args)
            verify_zip(entry, zip_path)
            safe_extract(zip_path, restore_dir)
            downloaded_roles.append(str(role))

        restored_market_sqlite = restore_dir / "market.sqlite"
        sqlite_stats = validate_market_sqlite(restored_market_sqlite)

        if args.verify_only:
            print(json.dumps({
                "ok": True,
                "action": "download-verify",
                "snapshot": args.snapshot,
                "trade_date": manifest.get("trade_date", ""),
                "downloaded_roles": downloaded_roles,
                "stats": sqlite_stats,
            }, ensure_ascii=False, indent=2))
            return

        backup_path = backup_existing_market_sqlite()
        final_market_sqlite = data_center_path("market.sqlite")
        tmp_market_sqlite = final_market_sqlite.with_suffix(".sqlite.oss_tmp")
        shutil.copy2(restored_market_sqlite, tmp_market_sqlite)
        validate_market_sqlite(tmp_market_sqlite)
        tmp_market_sqlite.replace(final_market_sqlite)

        for relative_dir in ("Archives/sqlite", "MarketLake", "Cache", "SwiftData"):
            source_dir = restore_dir / relative_dir
            if source_dir.exists():
                target_dir = DATACENTER_DIR / relative_dir
                target_dir.mkdir(parents=True, exist_ok=True)
                for path in source_dir.rglob("*"):
                    if path.is_file():
                        output = target_dir / path.relative_to(source_dir)
                        output.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(path, output)
        restored_duckdb = restore_dir / "market.duckdb"
        if restored_duckdb.exists():
            shutil.copy2(restored_duckdb, data_center_path("market.duckdb"))

        local_manifest = DATACENTER_DIR / "oss_snapshot_manifest.json"
        local_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        print(json.dumps({
            "ok": True,
            "action": "download",
            "snapshot": args.snapshot,
            "trade_date": manifest.get("trade_date", ""),
            "downloaded_roles": downloaded_roles,
            "backup": str(backup_path) if backup_path else None,
            "market_sqlite": str(final_market_sqlite),
            "stats": sqlite_stats,
        }, ensure_ascii=False, indent=2))


def command_verify(args: argparse.Namespace) -> None:
    market_sqlite = Path(args.db_path) if args.db_path else data_center_path("market.sqlite")
    stats = validate_market_sqlite(market_sqlite)
    result = {
        "ok": True,
        "action": "verify",
        "market_sqlite": str(market_sqlite),
        "stats": stats,
        "sha256": sha256_file(market_sqlite),
        "size": market_sqlite.stat().st_size,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--bucket", default=os.environ.get("ALIYUN_OSS_BUCKET"), help="OSS bucket name")
    parser.add_argument("--prefix", default=os.environ.get("STOCKMASTER_OSS_PREFIX", DEFAULT_PREFIX), help="OSS object prefix")
    parser.add_argument("--ossutil", default=os.environ.get("STOCKMASTER_OSSUTIL"), help="ossutil executable path")
    parser.add_argument(
        "--oss-config-file",
        default=os.environ.get("STOCKMASTER_OSS_CONFIG_FILE"),
        help="ossutil config file path",
    )
    parser.add_argument(
        "--public-base-url",
        default=os.environ.get("STOCKMASTER_OSS_PUBLIC_BASE_URL"),
        help="Public or signed base URL for downloads, for example https://bucket.endpoint",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="StockMaster OSS database snapshot tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    upload = subparsers.add_parser("upload", help="Build and upload database snapshot")
    add_common_args(upload)
    upload.add_argument("--version", help="Snapshot version, default today")
    upload.add_argument("--include-archives", action="store_true", help="Package Archives/sqlite")
    upload.add_argument("--include-lake", action="store_true", help="Package MarketLake")
    upload.add_argument("--include-cache", action="store_true", help="Package Cache")
    upload.add_argument("--include-swiftdata", action="store_true", help="Package SwiftData local store")
    upload.add_argument("--include-duckdb", action="store_true", help="Package market.duckdb")
    upload.add_argument(
        "--include-runtime",
        action="store_true",
        help="Package ignored runtime data: Archives/sqlite, MarketLake, Cache, SwiftData, and market.duckdb",
    )
    upload.add_argument("--publish-monthly", action="store_true", help="Also publish monthly snapshot")
    upload.add_argument("--month", help="Monthly snapshot directory, default yyyy-MM")
    upload.set_defaults(func=command_upload)

    download = subparsers.add_parser("download", help="Download and restore database snapshot")
    add_common_args(download)
    download.add_argument("--snapshot", default="latest", help="Snapshot path under snapshots/, default latest")
    download.add_argument("--include-archives", action="store_true", help="Restore Archives/sqlite package")
    download.add_argument("--include-lake", action="store_true", help="Restore MarketLake package")
    download.add_argument("--include-cache", action="store_true", help="Restore Cache package")
    download.add_argument("--include-swiftdata", action="store_true", help="Restore SwiftData local store package")
    download.add_argument("--include-duckdb", action="store_true", help="Restore market.duckdb package")
    download.add_argument(
        "--include-runtime",
        action="store_true",
        help="Restore ignored runtime data: Archives/sqlite, MarketLake, Cache, SwiftData, and market.duckdb",
    )
    download.add_argument("--verify-only", action="store_true", help="Download and verify without replacing local files")
    download.set_defaults(func=command_download)

    verify = subparsers.add_parser("verify", help="Verify local market.sqlite")
    verify.add_argument("--db-path", help="SQLite path, default DataCenter/market.sqlite")
    verify.set_defaults(func=command_verify)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
