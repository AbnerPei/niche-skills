---
name: stockmaster-region-data
description: >
  获取和刷新 StockMaster 地区数据。用户提到 RegionData.json、省市区数据、地区数据、
  fetch_regions.py、StockMaster/Tools/RegionData.json 时应使用。本技能只负责地区数据。
---

# StockMaster 地区数据

## 概述

本 Skill 封装 StockMaster 地区数据脚本，支持：
- 从公开行政区划接口获取省市区数据
- 生成或刷新 `StockMaster/Tools/RegionData.json`

## 资源文件

| 文件 | 说明 |
|------|------|
| `scripts/fetch_regions.py` | 地区数据获取脚本 |
| `references/examples.md` | 常见调用示例 |
| `references/install-guide.md` | 安装和环境变量说明 |
| `requirements.txt` | Python 依赖声明 |

## 前置条件

- Python 3.8+
- 设置 `STOCKMASTER_ROOT` 指向 StockMaster 项目根目录
- 本脚本使用 Python 标准库，无第三方依赖

## 脚本路径

```bash
{skill_path}/scripts/fetch_regions.py
```

## 用法

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
python3 {skill_path}/scripts/fetch_regions.py
```

## 工作流程

1. 确认用户要更新地区数据。
2. 检查 `STOCKMASTER_ROOT/StockMaster/Tools` 是否存在。
3. 运行 `fetch_regions.py`。
4. 返回 `RegionData.json` 输出位置。

## 注意事项

- 行政区划接口可能变化，失败时保留错误输出并检查接口响应。
- 本 Skill 不处理股票或行情数据。
