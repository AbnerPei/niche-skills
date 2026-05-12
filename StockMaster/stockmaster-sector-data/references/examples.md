# 使用示例

## 刷新同花顺行业板块汇总

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
python3 {skill_path}/scripts/fetch_sector_data.py --date 2026-05-04 --source ths --summary-only
```

## 输出 JSON 给 App 解析

```bash
python3 {skill_path}/scripts/fetch_sector_data.py --date 2026-05-04 --source ths --summary-only --json
```

## 抓取能源金属详情页

```bash
python3 {skill_path}/scripts/fetch_sector_data.py --date 2026-05-04 --source ths --with-components --sector-code 881267 --component-limit 1 --json
```
