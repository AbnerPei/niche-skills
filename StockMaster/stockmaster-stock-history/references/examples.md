# 使用示例

## 查看参数

```bash
python3 {skill_path}/scripts/fetch_single_stock.py --help
python3 {skill_path}/scripts/fetch_all_stocks.py --help
python3 {skill_path}/scripts/real_time_stock_fetcher.py --help
python3 {skill_path}/scripts/update_stock_data.py --help
```

## 获取单股历史行情

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
python3 {skill_path}/scripts/fetch_single_stock.py --code 000001
```

## 批量获取 StockMaster JSON

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
python3 {skill_path}/scripts/fetch_all_stocks.py
```

## 抓取原始 CSV

```bash
export STOCKMASTER_STOCK_LIST_DATA_DIR="/path/to/output/stock_list"
python3 {skill_path}/scripts/real_time_stock_fetcher.py
```
