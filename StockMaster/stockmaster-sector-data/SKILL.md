---
name: stockmaster-sector-data
description: >
  抓取和刷新 StockMaster 板块数据。用户提到同花顺行业板块、板块快照、
  sector_sources.sqlite、能源金属、Scrapling、stockmaster-sector-data 或板块手动刷新时应使用。
---

# StockMaster 板块数据

## 概述

本 Skill 负责把同花顺行业板块等板块数据写入 StockMaster 的 `DataCenter/sector_sources.sqlite`。

## 资源文件

| 文件 | 说明 |
|------|------|
| `scripts/fetch_sector_data.py` | 抓取板块汇总和详情数据 |
| `references/examples.md` | 常见调用示例 |
| `requirements.txt` | Python 依赖声明 |

## 前置条件

- Python 3.8+
- 设置 `STOCKMASTER_ROOT` 指向 StockMaster 项目根目录
- 可选设置 `STOCKMASTER_DATA_CENTER` 指向运行时 DataCenter

## 用法

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
python3 {skill_path}/scripts/fetch_sector_data.py --date 2026-05-04 --source ths --summary-only --json
python3 {skill_path}/scripts/fetch_sector_data.py --date 2026-05-04 --source ths --with-components --sector-code 881267 --component-limit 1 --json
```

## 注意事项

- 股票代码和板块代码保持字符串。
- 如果请求日期不是 A 股交易日，脚本会回退到最后一个可用交易日，并由 App 展示提示。
- 抓取产物写入项目 `DataCenter/sector_sources.sqlite`，不提交抓取缓存、HTML 或日志。
