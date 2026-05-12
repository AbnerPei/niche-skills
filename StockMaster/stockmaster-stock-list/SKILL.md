---
name: stockmaster-stock-list
description: >
  获取、更新、检查或调试 StockMaster A 股股票列表。用户提到获取股票列表、全市场股票、
  沪深北股票、SSE、SZSE、BSE、ST 股票、run_stocks_fetcher、all_stocks_fetcher、
  st_stocks_fetcher、股票列表 CSV 时应使用。本技能只负责股票列表和 ST 列表。
---

# StockMaster 股票列表

## 概述

本 Skill 封装 StockMaster 的股票列表脚本，支持：
- 获取沪市、深市、北交所股票基础列表
- 生成全市场股票 CSV
- 获取 ST 股票列表
- 输出 `recent_listed_ipos.csv` 与 `pending_ipos.csv`
- 为历史行情批量抓取提供股票清单

## 资源文件

| 文件 | 说明 |
|------|------|
| `scripts/run_stocks_fetcher.py` | 股票列表统一入口 |
| `scripts/all_stocks_fetcher.py` | 全市场股票列表获取器 |
| `scripts/st_stocks_fetcher.py` | ST 股票列表获取器 |
| `references/examples.md` | 常见调用示例 |
| `references/install-guide.md` | 安装和环境变量说明 |
| `requirements.txt` | Python 依赖声明 |

## 前置条件

- Python 3.8+
- 安装依赖：`python3 -m pip install -r "{skill_path}/requirements.txt"`
- 建议设置 `STOCKMASTER_STOCK_LIST_DATA_DIR` 指向股票列表输出目录

## 脚本路径

```bash
{skill_path}/scripts/run_stocks_fetcher.py
{skill_path}/scripts/all_stocks_fetcher.py
{skill_path}/scripts/st_stocks_fetcher.py
```

## 用法

```bash
python3 {skill_path}/scripts/run_stocks_fetcher.py --help
python3 {skill_path}/scripts/st_stocks_fetcher.py --help
```

## 工作流程

1. 用户要普通股票列表时，优先运行 `run_stocks_fetcher.py`。
2. 用户明确要 ST 股票时，运行 `st_stocks_fetcher.py`。
3. 将输出目录记录给用户；历史行情类任务需要复用该目录。
4. 不把生成的 CSV、日志和缓存提交到 skill 仓库。

## 注意事项

- 历史行情批量脚本依赖股票列表 CSV；如果缺失，先运行本 Skill。
- 交易所接口字段可能变化，解析失败时先用小范围命令复现，再调整脚本。
