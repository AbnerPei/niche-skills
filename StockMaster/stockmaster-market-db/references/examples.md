# 使用示例

## 查看参数

```bash
python3 {skill_path}/scripts/build_market_db.py --help
python3 {skill_path}/scripts/import_json_to_db.py --help
```

## 从 JSON 导入 SQLite

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
python3 {skill_path}/scripts/import_json_to_db.py
```

## 构建市场数据库

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
export STOCKMASTER_FETCH_SINGLE_SCRIPT="{stockmaster_stock_history_path}/scripts/fetch_single_stock.py"
python3 {skill_path}/scripts/build_market_db.py
```

## 归档热库与导出分析湖

```bash
python3 {skill_path}/scripts/archive_market_sqlite.py --execute --hot-years 3
python3 {skill_path}/scripts/export_market_lake.py
```

## OSS 数据库快照

```bash
python3 {skill_path}/scripts/oss_snapshot.py verify
python3 {skill_path}/scripts/oss_snapshot.py upload --include-runtime --publish-monthly
python3 {skill_path}/scripts/oss_snapshot.py download --include-runtime
```

`--include-runtime` 会额外上传/恢复 `Archives/sqlite`、`MarketLake`、`Cache`、`SwiftData` 和 `market.duckdb`。`Cache` 打包时会自动排除 `ossutilconfig`、`ossutil-wrapper.sh`。只同步行情主库时不要加这个参数。

## 输出检查

重点检查 StockMaster 项目中的 `DataCenter/market.sqlite` 或脚本参数指定的数据库路径。
