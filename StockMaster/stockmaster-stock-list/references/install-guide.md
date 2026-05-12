# 安装说明

## 安装 Skill

```bash
git clone https://github.com/AbnerPei/niche-skills.git
mkdir -p ~/.codex/skills
ln -s /path/to/niche-skills/StockMaster/stockmaster-stock-list ~/.codex/skills/stockmaster-stock-list
```

## 安装依赖

```bash
python3 -m venv .venv
.venv/bin/pip install -r /path/to/niche-skills/StockMaster/stockmaster-stock-list/requirements.txt
```

## 环境变量

```bash
export STOCKMASTER_STOCK_LIST_DATA_DIR="/path/to/output/stock_list"
```

如果不设置，脚本会按自身默认逻辑输出到当前工作目录或脚本默认目录。
