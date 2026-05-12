# StockMaster 市场数据库 Skill 使用指南

## 适用场景

当你需要构建 `market.sqlite`，或将 `DataCenter/StockData` 中的 JSON K 线导入 SQLite 时，使用 `stockmaster-market-db`。

## 安装

```bash
git clone https://github.com/AbnerPei/niche-skills.git
mkdir -p ~/.codex/skills
ln -s /path/to/niche-skills/StockMaster/stockmaster-market-db ~/.codex/skills/stockmaster-market-db
python3 -m pip install -r /path/to/niche-skills/StockMaster/stockmaster-market-db/requirements.txt
```

## 基本配置

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
export STOCKMASTER_FETCH_SINGLE_SCRIPT="/path/to/niche-skills/StockMaster/stockmaster-stock-history/scripts/fetch_single_stock.py"
```

`STOCKMASTER_FETCH_SINGLE_SCRIPT` 只在构建过程中需要补抓单股行情时使用。

## 常用命令

```bash
python3 /path/to/niche-skills/StockMaster/stockmaster-market-db/scripts/build_market_db.py --help
python3 /path/to/niche-skills/StockMaster/stockmaster-market-db/scripts/import_json_to_db.py --help
```

## 输出位置

默认数据库路径是 `STOCKMASTER_ROOT/StockMaster/DataCenter/market.sqlite`。
