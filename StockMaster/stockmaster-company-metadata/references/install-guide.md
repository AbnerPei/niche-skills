# 安装说明

## 安装 Skill

```bash
git clone https://github.com/AbnerPei/niche-skills.git
mkdir -p ~/.codex/skills
ln -s /path/to/niche-skills/StockMaster/stockmaster-company-metadata ~/.codex/skills/stockmaster-company-metadata
```

## 安装依赖

```bash
python3 -m venv .venv
.venv/bin/pip install -r /path/to/niche-skills/StockMaster/stockmaster-company-metadata/requirements.txt
```

## 环境变量

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
```

脚本会读取 `$STOCKMASTER_ROOT/StockMaster/DataCenter/StockData`，并写入 `$STOCKMASTER_ROOT/StockMaster/DataCenter/companies_metadata.json`。
