# 安装说明

## 安装 Skill

```bash
git clone https://github.com/AbnerPei/niche-skills.git
mkdir -p ~/.codex/skills
ln -s /path/to/niche-skills/StockMaster/stockmaster-region-data ~/.codex/skills/stockmaster-region-data
```

## 安装依赖

本 Skill 只使用 Python 标准库，无需安装第三方依赖。

## 环境变量

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
```

脚本会写入 `$STOCKMASTER_ROOT/StockMaster/Tools/RegionData.json`。
