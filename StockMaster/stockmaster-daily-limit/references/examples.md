# 使用示例

## 查看参数

```bash
python3 {skill_path}/scripts/smart_daily_limit_fetcher.py --help
python3 {skill_path}/scripts/fetch_limit_up_history.py --help
```

## 获取每日涨停

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
python3 {skill_path}/scripts/smart_daily_limit_fetcher.py
```

## 根据涨停列表同步历史行情

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
export STOCKMASTER_FETCH_SINGLE_SCRIPT="{stockmaster_stock_history_path}/scripts/fetch_single_stock.py"
python3 {skill_path}/scripts/fetch_limit_up_history.py
```

## 输出检查

重点检查：
- `StockMaster/DataCenter/LimitUp`
- `StockMaster/DataCenter/StockData`
- `STOCKMASTER_SCRIPT_LOG_DIR`
