# 安装说明

## 安装 Skill

```bash
git clone https://github.com/AbnerPei/niche-skills.git
mkdir -p ~/.codex/skills
ln -s /path/to/niche-skills/StockMaster/stockmaster-stock-history ~/.codex/skills/stockmaster-stock-history
```

## 安装依赖

```bash
python3 -m venv .venv
.venv/bin/pip install -r /path/to/niche-skills/StockMaster/stockmaster-stock-history/requirements.txt
```

## 环境变量

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
export STOCKMASTER_STOCK_LIST_DATA_DIR="/path/to/stock_list_csv_dir"
```

`real_time_stock_fetcher.py` 依赖股票列表 CSV；没有 CSV 时先安装并运行 `stockmaster-stock-list`。
