# 安装说明

## 安装 Skill

```bash
git clone https://github.com/AbnerPei/niche-skills.git
mkdir -p ~/.codex/skills
ln -s /path/to/niche-skills/StockMaster/stockmaster-market-db ~/.codex/skills/stockmaster-market-db
```

## 安装依赖

```bash
python3 -m venv .venv
.venv/bin/pip install -r /path/to/niche-skills/StockMaster/stockmaster-market-db/requirements.txt
```

## 环境变量

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
export STOCKMASTER_FETCH_SINGLE_SCRIPT="/path/to/stockmaster-stock-history/scripts/fetch_single_stock.py"
export ALIYUN_OSS_BUCKET="your-stockmaster-bucket"
export STOCKMASTER_OSS_PREFIX="stockmaster"
```

`STOCKMASTER_FETCH_SINGLE_SCRIPT` 只在构建库时需要补抓单股行情的场景使用。
OSS 快照命令还需要本机已安装 `ossutil`。可以提前运行 `ossutil config`，也可以在 StockMaster 设置中心填写 Bucket、Region、AccessKey、Prefix 和 ossutil 路径，由 App 运行时生成本机 ossutil config；下载公开对象时也可设置 `STOCKMASTER_OSS_PUBLIC_BASE_URL`。
