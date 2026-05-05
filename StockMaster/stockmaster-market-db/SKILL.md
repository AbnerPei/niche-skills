---
name: stockmaster-market-db
description: >
  构建或导入 StockMaster SQLite 市场数据库。用户提到 market.sqlite、市场数据库、
  SQLite、build_market_db、import_json_to_db、DataCenter JSON 入库、stocks/daily_bars/
  fetch_status 表结构时应使用。本技能只负责市场库构建和导入。
---

# StockMaster 市场数据库

## 概述

本 Skill 封装 StockMaster 市场数据库脚本，支持：
- 从股票列表和日 K 行情构建 `market.sqlite`
- 将 `DataCenter/StockData` 中的 JSON K 线导入 SQLite
- 检查股票、日线和抓取状态相关表
- 将历史年份归档到年度 SQLite
- 导出 Parquet 分析湖
- 上传、下载和校验阿里云 OSS 数据库快照；可选包含 `Archives`、`MarketLake`、`Cache`、`SwiftData` 和 `market.duckdb`

## 资源文件

| 文件 | 说明 |
|------|------|
| `scripts/build_market_db.py` | 构建市场 SQLite 数据库 |
| `scripts/import_json_to_db.py` | 将 JSON K 线导入 SQLite |
| `scripts/archive_market_sqlite.py` | 归档冷年份并裁剪热库 |
| `scripts/export_market_lake.py` | 导出 MarketLake Parquet |
| `scripts/oss_snapshot.py` | OSS 数据库快照上传、下载、校验 |
| `references/examples.md` | 常见调用示例 |
| `references/install-guide.md` | 安装和环境变量说明 |
| `requirements.txt` | Python 依赖声明 |

## 前置条件

- Python 3.8+
- 设置 `STOCKMASTER_ROOT` 指向 StockMaster 项目根目录
- 如果需要实时补抓行情，确保 `stockmaster-stock-history` skill 可用，或设置 `STOCKMASTER_FETCH_SINGLE_SCRIPT`

## 脚本路径

```bash
{skill_path}/scripts/build_market_db.py
{skill_path}/scripts/import_json_to_db.py
```

## 用法

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
python3 {skill_path}/scripts/build_market_db.py --help
python3 {skill_path}/scripts/import_json_to_db.py --help
python3 {skill_path}/scripts/archive_market_sqlite.py --help
python3 {skill_path}/scripts/export_market_lake.py --help
python3 {skill_path}/scripts/oss_snapshot.py verify
python3 {skill_path}/scripts/oss_snapshot.py upload --include-runtime --publish-monthly
python3 {skill_path}/scripts/oss_snapshot.py download --include-runtime
```

## 工作流程

1. 从现有 JSON 入库时，优先运行 `import_json_to_db.py`。
2. 需要完整构建或补抓时，运行 `build_market_db.py`。
3. 构建前确认 `DataCenter/StockData` 和股票列表是否存在。
4. 数据库、日志、临时文件都是运行产物，不提交到 skill 仓库。

## 注意事项

- SQLite 产物通常写到 StockMaster 项目的 `DataCenter` 下。
- 如果缺失历史行情，先用 `stockmaster-stock-history` 补齐。
- OSS AccessKey 只放在本机环境或 ossutil 配置中，不写进仓库。
- `--include-runtime` 会打包本机运行状态，包含 SwiftData；跨设备恢复前应确认目标设备可以覆盖本地状态。
- `Cache` 打包时会自动排除 `ossutilconfig`、`ossutil-wrapper.sh` 这类本机敏感文件，避免把 OSS 凭据上传到对象存储。
- 上传流程会先写入 `.staging/`，发布 `latest/` 和可选 `monthly/` 成功后自动清空 `.staging/`；建议同时在 OSS 配置 1 天生命周期规则，兜底清理异常中断时留下的 staging 残留。
