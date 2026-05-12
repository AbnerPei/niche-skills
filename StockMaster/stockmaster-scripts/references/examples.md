# 路由示例

## 每日涨停

使用 `stockmaster-daily-limit`，不要在总路由 skill 中执行脚本。

## 获取股票列表

使用 `stockmaster-stock-list`。

## 股票列表到市场库的完整链路

1. `stockmaster-stock-list` 生成股票列表 CSV
2. `stockmaster-stock-history` 生成历史行情 JSON
3. `stockmaster-market-db` 导入或构建 SQLite

## 公司元数据

使用 `stockmaster-company-metadata`，它依赖已有 `StockData` JSON。
