---
name: stockmaster-scripts
description: >
  StockMaster 脚本总路由 Skill。用户提出 StockMaster 脚本、ap-stock-scripts、
  ap-scripts-env、每日涨停、股票列表、历史行情、市场数据库、公司元数据、地区数据、
  等综合任务，但未明确子 skill 时应使用。本技能只负责选择并调用独立子 skill。
---

# StockMaster 脚本总路由

## 概述

本 Skill 是 StockMaster 脚本集合的入口，只负责把任务路由到独立子 Skill，不维护真实业务脚本。

## 子 Skill

| 任务 | 子 Skill |
|------|----------|
| 每日涨停、涨停历史同步 | `stockmaster-daily-limit` |
| 股票列表、ST 股票 | `stockmaster-stock-list` |
| 单股/批量历史行情、原始 CSV | `stockmaster-stock-history` |
| SQLite 市场数据库 | `stockmaster-market-db` |
| OSS 数据库快照、SQLite 归档、分析湖导出 | `stockmaster-market-db` |
| 同花顺行业板块、板块快照 | `stockmaster-sector-data` |
| DuckDB 策略选股、策略结果写回 | `stockmaster-strategy-engine` |
| 公司元数据 | `stockmaster-company-metadata` |
| 省市区地区数据 | `stockmaster-region-data` |

## 工作流程

1. 先根据用户描述选择最具体的子 Skill。
2. 如果一个任务涉及多个步骤，按依赖顺序调用子 Skill：股票列表 -> 历史行情 -> 市场数据库。
3. 需要详细命令时读取 `references/route-map.md`。
4. 不在本 Skill 中复制或改写业务脚本；业务脚本归属各自子 Skill。

## 注意事项

- 用户明确说“每日涨停”时，直接使用 `stockmaster-daily-limit`。
- 用户明确说“获取股票列表”时，直接使用 `stockmaster-stock-list`。
- 用户只说“StockMaster 脚本”或“这些脚本怎么用”时，先使用本路由 Skill。
