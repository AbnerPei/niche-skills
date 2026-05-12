# Route Map

## Script Entrypoints

- `stockmaster-daily-limit` -> `stockmaster-daily-limit/scripts/smart_daily_limit_fetcher.py`
- `stockmaster-limit-history` -> `stockmaster-daily-limit/scripts/fetch_limit_up_history.py`
- `stockmaster-stock-list` -> `stockmaster-stock-list/scripts/run_stocks_fetcher.py`
- `stockmaster-st-list` -> `stockmaster-stock-list/scripts/st_stocks_fetcher.py`
- `stockmaster-fetch-stock` -> `stockmaster-stock-history/scripts/fetch_single_stock.py`
- `stockmaster-fetch-all-stocks` -> `stockmaster-stock-history/scripts/fetch_all_stocks.py`
- `stockmaster-real-stock-fetcher` -> `stockmaster-stock-history/scripts/real_time_stock_fetcher.py`
- `stockmaster-update-stock-data` -> `stockmaster-stock-history/scripts/update_stock_data.py`
- `stockmaster-market-db` -> `stockmaster-market-db/scripts/build_market_db.py`
- `stockmaster-import-json-db` -> `stockmaster-market-db/scripts/import_json_to_db.py`
- `stockmaster-archive-market-db` -> `stockmaster-market-db/scripts/archive_market_sqlite.py`
- `stockmaster-export-market-lake` -> `stockmaster-market-db/scripts/export_market_lake.py`
- `stockmaster-oss-upload-snapshot` -> `stockmaster-market-db/scripts/oss_snapshot.py upload`
- `stockmaster-oss-download-snapshot` -> `stockmaster-market-db/scripts/oss_snapshot.py download`
- `stockmaster-oss-verify-snapshot` -> `stockmaster-market-db/scripts/oss_snapshot.py verify`
- `stockmaster-sector-data` -> `stockmaster-sector-data/scripts/fetch_sector_data.py`
- `stockmaster-strategy-engine` -> `stockmaster-strategy-engine/scripts/build_strategy_duckdb.py`
- `stockmaster-company-metadata` -> `scripts/company_metadata/【脚本】同步公司元数据.py`
- `stockmaster-region-data` -> `scripts/region_data/fetch_regions.py`

## Original Project Compatibility

Original StockMaster and `ap-stock-scripts` Python entrypoints should stay as thin wrappers that execute the concrete scripts in `niche-skills/StockMaster/<skill>/scripts`.

## Data Outputs

- Generated stock-list CSVs: `data/stock_list/`
- Raw historical CSVs: `data/real_time_data/`
- Logs: `logs/`
- StockMaster app JSON/SQLite outputs still live under `STOCKMASTER_ROOT/StockMaster/DataCenter`.
