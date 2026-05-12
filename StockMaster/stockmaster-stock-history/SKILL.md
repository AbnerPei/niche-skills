---
name: stockmaster-stock-history
description: >
  获取和更新 StockMaster 股票历史行情数据。用户提到单股 K 线、批量历史行情、
  fetch_single_stock、fetch_all_stocks、real_time_stock_fetcher、update_stock_data、
  250 日原始 CSV、StockMaster/DataCenter/StockData 时应使用。本技能只负责历史行情。
---

# StockMaster 历史行情

## 概述

本 Skill 封装 StockMaster 的历史行情脚本，支持：
- 获取单只股票历史 K 线 JSON
- 批量补齐 StockMaster `DataCenter/StockData`
- 抓取原始 250 日 CSV 历史行情
- 更新既有股票数据

## 资源文件

| 文件 | 说明 |
|------|------|
| `scripts/fetch_single_stock.py` | 单只股票历史行情获取 |
| `scripts/fetch_all_stocks.py` | 批量历史行情获取 |
| `scripts/real_time_stock_fetcher.py` | 原始 250 日 CSV 批量抓取 |
| `scripts/update_stock_data.py` | 股票数据更新工具 |
| `references/examples.md` | 常见调用示例 |
| `references/install-guide.md` | 安装和环境变量说明 |
| `requirements.txt` | Python 依赖声明 |

## 前置条件

- Python 3.8+
- 安装依赖：`python3 -m pip install -r "{skill_path}/requirements.txt"`
- 设置 `STOCKMASTER_ROOT` 指向 StockMaster 项目根目录
- 批量原始 CSV 抓取前，先使用 `stockmaster-stock-list` 生成股票列表

## 脚本路径

```bash
{skill_path}/scripts/fetch_single_stock.py
{skill_path}/scripts/fetch_all_stocks.py
{skill_path}/scripts/real_time_stock_fetcher.py
{skill_path}/scripts/update_stock_data.py
```

## 用法

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
python3 {skill_path}/scripts/fetch_single_stock.py --help
python3 {skill_path}/scripts/fetch_all_stocks.py --help
python3 {skill_path}/scripts/real_time_stock_fetcher.py --help
```

## 工作流程

1. 单只股票任务用 `fetch_single_stock.py`。
2. 批量 StockMaster JSON 任务用 `fetch_all_stocks.py`。
3. 原始 CSV 或 250 日批量抓取用 `real_time_stock_fetcher.py`，先确认股票列表 CSV 已存在。
4. 增量更新既有数据用 `update_stock_data.py`。

## 注意事项

- 如果脚本提示缺少股票列表，先运行 `stockmaster-stock-list`。
- 数据输出属于运行产物，不能提交到 skill 仓库。
- 构建 SQLite 时转交 `stockmaster-market-db`。
