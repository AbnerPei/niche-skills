# StockMaster 板块数据 Skill 使用指南

## 适用场景

当你需要抓取同花顺行业板块、刷新板块快照、写入 `sector_sources.sqlite`，或排查某个板块成分数据时，使用 `stockmaster-sector-data`。

## 安装

```bash
git clone https://github.com/AbnerPei/niche-skills.git
mkdir -p ~/.codex/skills
ln -s /path/to/niche-skills/StockMaster/stockmaster-sector-data ~/.codex/skills/stockmaster-sector-data
python3 -m pip install -r /path/to/niche-skills/StockMaster/stockmaster-sector-data/requirements.txt
```

## 基本配置

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
export STOCKMASTER_DATA_CENTER="$STOCKMASTER_ROOT/DataCenter"
```

如果不单独设置 `STOCKMASTER_DATA_CENTER`，脚本会按 `STOCKMASTER_ROOT/DataCenter` 解析运行时目录。

## 常用命令

```bash
python3 /path/to/niche-skills/StockMaster/stockmaster-sector-data/scripts/fetch_sector_data.py --date 2026-05-04 --source ths --summary-only --json

python3 /path/to/niche-skills/StockMaster/stockmaster-sector-data/scripts/fetch_sector_data.py --date 2026-05-04 --source ths --with-components --sector-code 881267 --component-limit 1 --json
```

## 输出位置

抓取结果会写入 StockMaster 项目的 `DataCenter/sector_sources.sqlite`。

不需要把抓取缓存、HTML 页面或临时日志提交到仓库。
