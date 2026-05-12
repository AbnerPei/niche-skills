# 安装说明

## 安装 Skill

从仓库复制本目录到 Codex skills 目录，或在支持 skills 的 IDE 中引用本目录：

```bash
git clone https://github.com/AbnerPei/niche-skills.git
mkdir -p ~/.codex/skills
ln -s /path/to/niche-skills/StockMaster/stockmaster-daily-limit ~/.codex/skills/stockmaster-daily-limit
```

## 安装依赖

```bash
python3 -m venv .venv
.venv/bin/pip install -r /path/to/niche-skills/StockMaster/stockmaster-daily-limit/requirements.txt
```

## 环境变量

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
export STOCKMASTER_PYTHON="/path/to/python"
export STOCKMASTER_SCRIPT_LOG_DIR="/path/to/logs"
export STOCKMASTER_FETCH_SINGLE_SCRIPT="/path/to/stockmaster-stock-history/scripts/fetch_single_stock.py"
```

`STOCKMASTER_FETCH_SINGLE_SCRIPT` 只在运行 `fetch_limit_up_history.py` 时需要。
