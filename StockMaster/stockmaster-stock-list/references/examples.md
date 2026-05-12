# 使用示例

## 查看参数

```bash
python3 {skill_path}/scripts/run_stocks_fetcher.py --help
python3 {skill_path}/scripts/st_stocks_fetcher.py --help
```

## 获取全市场股票列表

```bash
export STOCKMASTER_STOCK_LIST_DATA_DIR="/path/to/output/stock_list"
python3 {skill_path}/scripts/run_stocks_fetcher.py
```

运行后除了 `sse_stocks.csv` / `szse_stocks.csv` / `bse_stocks.csv`，还会额外生成：

```text
recent_listed_ipos.csv
pending_ipos.csv
```

- `recent_listed_ipos.csv`: 只保留源里有明确 `上市日期` 的新股
- `pending_ipos.csv`: 只保留 `上市日期` 为空的待上市新股

## 获取 ST 股票列表

```bash
python3 {skill_path}/scripts/st_stocks_fetcher.py --output-dir "/path/to/output/stock_list"
```

## 给历史行情使用

历史行情批量脚本需要能读到这里生成的 CSV：

```bash
export STOCKMASTER_STOCK_LIST_DATA_DIR="/path/to/output/stock_list"
```
