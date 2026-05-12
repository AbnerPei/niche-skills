# 使用示例

## 刷新地区数据

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
python3 {skill_path}/scripts/fetch_regions.py
```

## 输出检查

重点检查：

```text
StockMaster/Tools/RegionData.json
```

如果目标目录不存在，先确认 `STOCKMASTER_ROOT` 是否指向 StockMaster 项目根目录。
