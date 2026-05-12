---
name: stockmaster-company-metadata
description: >
  同步 StockMaster 公司元数据。用户提到 companies_metadata.json、公司元数据、
  行业信息、上市日期、AkShare 公司信息、【脚本】同步公司元数据.py 时应使用。
  本技能只负责从本地股票 JSON 补全公司 metadata。
---

# StockMaster 公司元数据

## 概述

本 Skill 封装 StockMaster 公司元数据同步脚本，支持：
- 扫描 `StockMaster/DataCenter/StockData` 中已有股票 JSON
- 通过 AkShare 查询公司行业、上市日期等元信息
- 更新 `StockMaster/DataCenter/companies_metadata.json`

## 资源文件

| 文件 | 说明 |
|------|------|
| `scripts/【脚本】同步公司元数据.py` | 公司元数据同步脚本 |
| `references/examples.md` | 常见调用示例 |
| `references/install-guide.md` | 安装和环境变量说明 |
| `requirements.txt` | Python 依赖声明 |

## 前置条件

- Python 3.8+
- 安装依赖：`python3 -m pip install -r "{skill_path}/requirements.txt"`
- 设置 `STOCKMASTER_ROOT` 指向 StockMaster 项目根目录
- 确保 `StockData` 下已有股票 JSON

## 脚本路径

```bash
{skill_path}/scripts/【脚本】同步公司元数据.py
```

## 用法

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
python3 {skill_path}/scripts/【脚本】同步公司元数据.py
```

## 工作流程

1. 先确认用户要同步公司 metadata，而不是股票历史行情本身。
2. 检查 `STOCKMASTER_ROOT` 和 `StockData` 是否存在。
3. 运行同步脚本。
4. 返回更新数量、失败股票和 `companies_metadata.json` 路径。

## 注意事项

- 若 `StockData` 为空，先使用 `stockmaster-stock-history` 拉取历史数据。
- AkShare 字段或接口变化时，先定位失败股票代码再修脚本。
