---
name: stockmaster-daily-limit
description: >
  获取并同步 StockMaster A 股每日涨停数据。用户提到每日涨停、涨停列表、涨停板、
  limit up、smart_daily_limit_fetcher、fetch_limit_up_history、同步涨停股票历史行情、
  StockMaster/DataCenter/LimitUp 时应使用。本技能只负责涨停相关流程。
---

# StockMaster 每日涨停

## 概述

本 Skill 封装 StockMaster 的每日涨停数据脚本，支持：
- 拉取指定日期或最近交易日的 A 股涨停列表
- 将涨停列表写入 StockMaster 项目的 `DataCenter/LimitUp`
- 根据涨停列表批量补齐对应股票的历史行情 JSON

## 资源文件

| 文件 | 说明 |
|------|------|
| `scripts/smart_daily_limit_fetcher.py` | 每日涨停智能获取脚本 |
| `scripts/fetch_limit_up_history.py` | 根据涨停列表同步历史行情 |
| `references/examples.md` | 常见调用示例 |
| `references/install-guide.md` | 安装和环境变量说明 |
| `requirements.txt` | Python 依赖声明 |

## 前置条件

- Python 3.8+
- 安装依赖：`python3 -m pip install -r "{skill_path}/requirements.txt"`
- 设置 `STOCKMASTER_ROOT` 指向本机 StockMaster 项目根目录
- 如需同步历史行情，确保 `stockmaster-stock-history` skill 可用，或设置 `STOCKMASTER_FETCH_SINGLE_SCRIPT`

## 脚本路径

```bash
{skill_path}/scripts/smart_daily_limit_fetcher.py
{skill_path}/scripts/fetch_limit_up_history.py
```

## 用法

```bash
export STOCKMASTER_ROOT="/path/to/StockMaster"
python3 {skill_path}/scripts/smart_daily_limit_fetcher.py --help
python3 {skill_path}/scripts/fetch_limit_up_history.py --help
```

## 工作流程

1. 先确认用户是要获取涨停列表，还是要按涨停列表补齐历史行情。
2. 获取涨停列表时运行 `smart_daily_limit_fetcher.py`，日期、输出路径按用户要求传入。
3. 同步历史行情时运行 `fetch_limit_up_history.py`；如果缺少历史行情脚本，提示安装或定位 `stockmaster-stock-history`。
4. 运行完成后说明输出位置和失败项，不把生成的 CSV、日志、缓存提交到仓库。

## 注意事项

- 数据源可能受交易日、节假日、接口限流影响，失败时优先小日期范围重试。
- 本 Skill 不负责获取股票基础列表；需要股票列表时使用 `stockmaster-stock-list`。
- 本 Skill 不负责构建 SQLite；需要市场库时使用 `stockmaster-market-db`。
