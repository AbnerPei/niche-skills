---
name: stockmaster-strategy-engine
description: >
  运行 StockMaster DuckDB 指标计算和配置化策略选股。用户提到策略选股、
  strategy_results、strategy_runs、build_strategy_duckdb、DuckDB 指标缓存、
  重新运行策略或 stockmaster-strategy-engine 时应使用。
---

# StockMaster 策略引擎

## 概述

本 Skill 负责读取 `market.sqlite`、构建/更新 `market.duckdb` 特征缓存，并把策略候选写回 SQLite。

## 资源文件

| 文件 | 说明 |
|------|------|
| `scripts/build_strategy_duckdb.py` | DuckDB 特征计算与策略结果写回 |
| `references/examples.md` | 常见调用示例 |
| `requirements.txt` | Python 依赖声明 |

## 前置条件

- Python 3.8+
- 设置 `STOCKMASTER_ROOT` 指向 StockMaster 项目根目录
- 可选设置 `STOCKMASTER_DATA_CENTER` 指向运行时 DataCenter

## 用法

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
python3 {skill_path}/scripts/build_strategy_duckdb.py \
  --sqlite-path "$STOCKMASTER_ROOT/DataCenter/market.sqlite" \
  --duckdb-path "$STOCKMASTER_ROOT/DataCenter/market.duckdb" \
  --strategy-file "$STOCKMASTER_ROOT/DataCenter/Strategies/v1_momentum_reversal.json" \
  --top 50
```

## 注意事项

- `market.duckdb` 是可重建缓存，不是长期唯一数据源。
- 策略结果最终写回 `market.sqlite` 的 `strategy_runs` / `strategy_results`。
- App 只读取写回结果，不直接嵌入 DuckDB。
