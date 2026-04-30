# 安装指南：Bilibili UP 主信息查询

## 前置条件

```bash
pip install requests
```

## 安装方式

> 路径说明：
> ```
> // 我的电脑上的niche-skills仓库地址
> /Users/peijianbo/Documents/AbnerPei/GitHub/niche-skills
>
> // 文档给的命令
> cp -r /路径/niche-skills/B站/bilibili-up-info ~/.codex/skills/
>
> // 实际你要执行的命令：
> cp -r /Users/peijianbo/Documents/AbnerPei/GitHub/niche-skills/B站/bilibili-up-info ~/.codex/skills/
>
> 直观一点，就是：
> 把 `路径` 更换为 `Users/peijianbo/Documents/AbnerPei/GitHub`
> ```

### 方式一：复制到你的 IDE 的 Skills 目录（推荐）

将 `bilibili-up-info` 目录**完整复制**到你的 IDE 对应的 Skills 目录下：

| IDE / 工具 | 安装命令 |
|-----------|---------|
| **CodeBuddy** | `cp -r /路径/niche-skills/B站/bilibili-up-info ~/.codebuddy/skills/` |
| **Cursor** | `cp -r /路径/niche-skills/B站/bilibili-up-info ~/.cursor/skills/` |
| **Codex** | `cp -r /路径/niche-skills/B站/bilibili-up-info ~/.codex/skills/` |
| **Claude Code** | `cp -r /路径/niche-skills/B站/bilibili-up-info ~/.claude/skills/` |
| **TRAE** | `cp -r /路径/niche-skills/B站/bilibili-up-info ~/.trae/skills/` |
| **Cline** | `cp -r /路径/niche-skills/B站/bilibili-up-info ~/.cline/skills/` |
| **Windsurf** | `cp -r /路径/niche-skills/B站/bilibili-up-info ~/.windsurf/skills/` |
| **其他 IDE** | 复制到对应 Tools / Skills 目录即可 |


如果对应目录不存在，先创建它：

```bash
mkdir -p ~/.codebuddy/skills   # CodeBuddy
mkdir -p ~/.cursor/skills      # Cursor
mkdir -p ~/.claude/skills      # Claude Code
mkdir -p ~/.trae/skills        # TRAE
# 以此类推……
```

### 方式二：通过全局 Skills 目录使用软链接（推荐）

在 `~/.agents/skills/` 下创建所有技能的软链接，后期 `git pull` 即可自动更新：

```bash
# 创建全局 Skills 目录
mkdir -p ~/.agents/skills

# 为每个技能创建软链接（指向仓库中的真实文件）
ln -s /你的路径/niche-skills/B站/bilibili-up-info ~/.agents/skills/bilibili-up-info
```

然后将你的 IDE 配置为读取 `~/.agents/skills/` 目录（部分工具原生支持，不支持的可以直接从该目录复制）。

> **软链接 ≈ 快捷方式**：创建后访问 `~/.agents/skills/bilibili-up-info` 就等于访问仓库里的真实文件。后续 `git pull` 更新代码后，技能自动更新，**无需重新安装**。


## 验证安装

安装后向 AI 提问：

> 帮我查一下 B 站 UP 主 163637592 的信息

如果返回了昵称（老师好我叫何同学）、简介、头像 URL 和空间链接，说明安装成功。

## 更新技能

```bash
cd niche-skills
git pull
```

- **软链接方式**：自动同步最新代码
- **复制方式**：手动重新复制一次即可

## 卸载技能

删除对应目录即可：

```bash
# 软链接方式
rm ~/.agents/skills/bilibili-up-info

# 复制方式
rm -rf ~/.codebuddy/skills/bilibili-up-info
```

仓库里的源文件不受影响。

## 故障排查

### "requests 模块未找到"

```bash
pip3 install requests
```

### 脚本返回风控错误

如果遇到 `风控校验失败` 或 `请求过于频繁`，需要携带 Cookie：

```bash
python3 scripts/fetch_bilibili_up_info.py 163637592 --cookie "SESSDATA=xxx; bili_jct=xxx"
```

Cookie 可以从浏览器登录 B 站后获取（F12 → 网络 → 请求头中找到 Cookie 字段）。
