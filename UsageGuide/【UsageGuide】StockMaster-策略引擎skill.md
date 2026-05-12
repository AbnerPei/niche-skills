# StockMaster 策略引擎 Skill 使用指南

## 适用场景

当你需要基于 `market.sqlite` 重新构建 `market.duckdb` 特征缓存、执行配置化策略选股，或检查 `strategy_runs` / `strategy_results` 写回结果时，使用 `stockmaster-strategy-engine`。

## 安装

```bash
git clone https://github.com/AbnerPei/niche-skills.git
mkdir -p ~/.codex/skills
ln -s /path/to/niche-skills/StockMaster/stockmaster-strategy-engine ~/.codex/skills/stockmaster-strategy-engine
python3 -m pip install -r /path/to/niche-skills/StockMaster/stockmaster-strategy-engine/requirements.txt
```

## 基本配置

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
export STOCKMASTER_DATA_CENTER="$STOCKMASTER_ROOT/DataCenter"
```

## 常用命令

```bash
python3 /path/to/niche-skills/StockMaster/stockmaster-strategy-engine/scripts/build_strategy_duckdb.py \
  --sqlite-path "$STOCKMASTER_ROOT/DataCenter/market.sqlite" \
  --duckdb-path "$STOCKMASTER_ROOT/DataCenter/market.duckdb" \
  --strategy-file "$STOCKMASTER_ROOT/DataCenter/Strategies/v1_momentum_reversal.json" \
  --top 50
```

## 输出位置

- DuckDB 特征缓存：`DataCenter/market.duckdb`
- 策略运行结果：写回 `market.sqlite` 的 `strategy_runs` / `strategy_results`

`market.duckdb` 是可重建缓存，真正给 App 使用的是最终写回 SQLite 的结果。
