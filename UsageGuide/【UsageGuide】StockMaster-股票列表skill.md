# StockMaster 股票列表 Skill 使用指南

## 适用场景

当你需要获取沪深北股票列表、全市场股票 CSV、ST 股票列表，或为历史行情批量抓取准备股票清单时，使用 `stockmaster-stock-list`。

## 安装

```bash
git clone https://github.com/AbnerPei/niche-skills.git
mkdir -p ~/.codex/skills
ln -s /path/to/niche-skills/StockMaster/stockmaster-stock-list ~/.codex/skills/stockmaster-stock-list
python3 -m pip install -r /path/to/niche-skills/StockMaster/stockmaster-stock-list/requirements.txt
```

## 基本配置

```bash
export STOCKMASTER_STOCK_LIST_DATA_DIR="/path/to/output/stock_list"
```

不设置时，脚本默认输出到 skill 目录下的 `data/stock_list`，该目录已被 `.gitignore` 忽略。

## 常用命令

```bash
python3 /path/to/niche-skills/StockMaster/stockmaster-stock-list/scripts/run_stocks_fetcher.py --help
python3 /path/to/niche-skills/StockMaster/stockmaster-stock-list/scripts/st_stocks_fetcher.py --help
```

## 输出位置

常见输出文件包括 `sse_stocks.csv`、`szse_stocks.csv`、`bse_stocks.csv` 和 ST 股票 CSV。
