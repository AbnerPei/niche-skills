# StockMaster 脚本路由 Skill 使用指南

## 适用场景

当用户只说“StockMaster 脚本”“这些股票脚本怎么用”，但没有明确具体业务时，使用 `stockmaster-scripts` 做路由。

## 安装

```bash
git clone https://github.com/AbnerPei/niche-skills.git
mkdir -p ~/.codex/skills
ln -s /path/to/niche-skills/StockMaster/stockmaster-scripts ~/.codex/skills/stockmaster-scripts
```

总路由 skill 不包含业务脚本依赖。真实任务应继续安装对应子 skill。

## 路由关系

| 任务 | 子 skill |
|------|----------|
| 每日涨停 | `stockmaster-daily-limit` |
| 股票列表 | `stockmaster-stock-list` |
| 历史行情 | `stockmaster-stock-history` |
| 市场数据库 | `stockmaster-market-db` |
| 公司元数据 | `stockmaster-company-metadata` |
| 地区数据 | `stockmaster-region-data` |
| 板块数据 | `stockmaster-sector-data` |
| 策略引擎 | `stockmaster-strategy-engine` |

## 推荐链路

股票列表 -> 历史行情 -> 市场数据库 -> 策略引擎。

每日涨停、公司元数据、地区数据、板块数据按需独立调用。
