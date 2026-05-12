# StockMaster 每日涨停 Skill 使用指南

## 适用场景

当你需要获取 A 股每日涨停列表、刷新 `DataCenter/LimitUp`，或根据涨停股票补齐历史行情时，使用 `stockmaster-daily-limit`。

## 安装

```bash
git clone https://github.com/AbnerPei/niche-skills.git
mkdir -p ~/.codex/skills
ln -s /path/to/niche-skills/StockMaster/stockmaster-daily-limit ~/.codex/skills/stockmaster-daily-limit
python3 -m pip install -r /path/to/niche-skills/StockMaster/stockmaster-daily-limit/requirements.txt
```

## 基本配置

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
export STOCKMASTER_PYTHON="/path/to/python"
```

如果需要同步涨停股票历史行情：

```bash
export STOCKMASTER_FETCH_SINGLE_SCRIPT="/path/to/niche-skills/StockMaster/stockmaster-stock-history/scripts/fetch_single_stock.py"
```

## 常用命令

```bash
python3 /path/to/niche-skills/StockMaster/stockmaster-daily-limit/scripts/smart_daily_limit_fetcher.py --help
python3 /path/to/niche-skills/StockMaster/stockmaster-daily-limit/scripts/fetch_limit_up_history.py --help
```

## 输出位置

默认写入 `STOCKMASTER_ROOT/StockMaster/DataCenter/LimitUp`。历史行情同步会写入 `STOCKMASTER_ROOT/StockMaster/DataCenter/StockData`。
