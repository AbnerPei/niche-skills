# StockMaster 公司元数据 Skill 使用指南

## 适用场景

当你需要根据本地股票 JSON 同步 `companies_metadata.json`、行业、上市日期等公司元数据时，使用 `stockmaster-company-metadata`。

## 安装

```bash
git clone https://github.com/AbnerPei/niche-skills.git
mkdir -p ~/.codex/skills
ln -s /path/to/niche-skills/StockMaster/stockmaster-company-metadata ~/.codex/skills/stockmaster-company-metadata
python3 -m pip install -r /path/to/niche-skills/StockMaster/stockmaster-company-metadata/requirements.txt
```

## 基本配置

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
```

## 常用命令

```bash
python3 /path/to/niche-skills/StockMaster/stockmaster-company-metadata/scripts/【脚本】同步公司元数据.py
```

## 输出位置

默认写入 `STOCKMASTER_ROOT/StockMaster/DataCenter/companies_metadata.json`。
