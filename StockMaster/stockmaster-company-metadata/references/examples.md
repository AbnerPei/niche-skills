# 使用示例

## 同步公司元数据

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
python3 {skill_path}/scripts/【脚本】同步公司元数据.py
```

## 输出检查

重点检查：
- `StockMaster/DataCenter/companies_metadata.json`
- 终端输出中的失败股票代码

如果 `StockData` 目录为空，先使用 `stockmaster-stock-history` 拉取股票历史行情。
