# StockMaster 历史行情 Skill 使用指南

## 适用场景

当你需要获取单只股票 K 线、批量刷新 `StockData`、抓取原始 250 日 CSV，或更新已有股票历史数据时，使用 `stockmaster-stock-history`。

## 安装

```bash
git clone https://github.com/AbnerPei/niche-skills.git
mkdir -p ~/.codex/skills
ln -s /path/to/niche-skills/StockMaster/stockmaster-stock-history ~/.codex/skills/stockmaster-stock-history
python3 -m pip install -r /path/to/niche-skills/StockMaster/stockmaster-stock-history/requirements.txt
```

## 基本配置

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
export STOCKMASTER_STOCK_LIST_DATA_DIR="/path/to/output/stock_list"
```

批量原始 CSV 抓取前，先使用 `stockmaster-stock-list` 生成股票列表。

## 常用命令

```bash
python3 /path/to/niche-skills/StockMaster/stockmaster-stock-history/scripts/fetch_single_stock.py --help
python3 /path/to/niche-skills/StockMaster/stockmaster-stock-history/scripts/fetch_all_stocks.py --help
python3 /path/to/niche-skills/StockMaster/stockmaster-stock-history/scripts/real_time_stock_fetcher.py --help
python3 /path/to/niche-skills/StockMaster/stockmaster-stock-history/scripts/update_stock_data.py --help
```

## 输出位置

StockMaster JSON 默认写入 `STOCKMASTER_ROOT/StockMaster/DataCenter/StockData`。原始 CSV 输出目录由脚本参数或当前工作目录决定。
