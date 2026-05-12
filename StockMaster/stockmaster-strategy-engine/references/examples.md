# 使用示例

## 运行默认策略

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
python3 {skill_path}/scripts/build_strategy_duckdb.py \
  --sqlite-path "$STOCKMASTER_ROOT/DataCenter/market.sqlite" \
  --duckdb-path "$STOCKMASTER_ROOT/DataCenter/market.duckdb" \
  --strategy-file "$STOCKMASTER_ROOT/DataCenter/Strategies/v1_momentum_reversal.json" \
  --top 50
```

## 仅查看参数

```bash
python3 {skill_path}/scripts/build_strategy_duckdb.py --help
```
