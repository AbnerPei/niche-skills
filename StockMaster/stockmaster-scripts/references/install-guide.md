# 安装说明

总路由 skill 本身不包含业务脚本依赖。安装时建议同时安装全部 StockMaster 子 skill：

```bash
git clone https://github.com/AbnerPei/niche-skills.git
mkdir -p ~/.codex/skills
ln -s /path/to/niche-skills/StockMaster/stockmaster-scripts ~/.codex/skills/stockmaster-scripts
ln -s /path/to/niche-skills/StockMaster/stockmaster-daily-limit ~/.codex/skills/stockmaster-daily-limit
ln -s /path/to/niche-skills/StockMaster/stockmaster-stock-list ~/.codex/skills/stockmaster-stock-list
ln -s /path/to/niche-skills/StockMaster/stockmaster-stock-history ~/.codex/skills/stockmaster-stock-history
ln -s /path/to/niche-skills/StockMaster/stockmaster-market-db ~/.codex/skills/stockmaster-market-db
ln -s /path/to/niche-skills/StockMaster/stockmaster-company-metadata ~/.codex/skills/stockmaster-company-metadata
ln -s /path/to/niche-skills/StockMaster/stockmaster-region-data ~/.codex/skills/stockmaster-region-data
```

业务依赖请进入具体子 skill 的 `references/install-guide.md` 查看。
