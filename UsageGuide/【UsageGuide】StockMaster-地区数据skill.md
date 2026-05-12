# StockMaster 地区数据 Skill 使用指南

## 适用场景

当你需要生成或刷新 `RegionData.json` 省市区数据时，使用 `stockmaster-region-data`。

## 安装

```bash
git clone https://github.com/AbnerPei/niche-skills.git
mkdir -p ~/.codex/skills
ln -s /path/to/niche-skills/StockMaster/stockmaster-region-data ~/.codex/skills/stockmaster-region-data
```

本 Skill 只使用 Python 标准库，无需第三方依赖。

## 基本配置

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
```

## 常用命令

```bash
python3 /path/to/niche-skills/StockMaster/stockmaster-region-data/scripts/fetch_regions.py
```

## 输出位置

默认写入 `STOCKMASTER_ROOT/StockMaster/Tools/RegionData.json`。
