# 安装指南：YouTube 博主信息查询

## 前置条件

```bash
pip install requests
```

## 安装方式

> 路径说明：
> ```
> // 我的电脑上的 niche-skills 仓库地址
> /Users/peijianbo/Documents/AbnerPei/GitHub/niche-skills
>
> // 文档给的命令
> cp -r /路径/niche-skills/YouTube/youtube-creator-info ~/.codex/skills/
>
> // 实际你要执行的命令：
> cp -r /Users/peijianbo/Documents/AbnerPei/GitHub/niche-skills/YouTube/youtube-creator-info ~/.codex/skills/
> ```

### 方式一：复制到你的 IDE 的 Skills 目录（推荐）

将 `youtube-creator-info` 目录完整复制到你的 IDE 对应的 Skills 目录下：

| IDE / 工具 | 安装命令 |
|-----------|---------|
| **CodeBuddy** | `cp -r /路径/niche-skills/YouTube/youtube-creator-info ~/.codebuddy/skills/` |
| **Cursor** | `cp -r /路径/niche-skills/YouTube/youtube-creator-info ~/.cursor/skills/` |
| **Codex** | `cp -r /路径/niche-skills/YouTube/youtube-creator-info ~/.codex/skills/` |
| **Claude Code** | `cp -r /路径/niche-skills/YouTube/youtube-creator-info ~/.claude/skills/` |
| **TRAE** | `cp -r /路径/niche-skills/YouTube/youtube-creator-info ~/.trae/skills/` |
| **Cline** | `cp -r /路径/niche-skills/YouTube/youtube-creator-info ~/.cline/skills/` |
| **Windsurf** | `cp -r /路径/niche-skills/YouTube/youtube-creator-info ~/.windsurf/skills/` |
| **其他 IDE** | 复制到对应 Tools / Skills 目录即可 |

如果对应目录不存在，先创建它：

```bash
mkdir -p ~/.codebuddy/skills
mkdir -p ~/.cursor/skills
mkdir -p ~/.claude/skills
mkdir -p ~/.trae/skills
```

### 方式二：通过全局 Skills 目录使用软链接（推荐）

在 `~/.agents/skills/` 下创建技能软链接，后期 `git pull` 即可自动更新：

```bash
mkdir -p ~/.agents/skills
ln -s /你的路径/niche-skills/YouTube/youtube-creator-info ~/.agents/skills/youtube-creator-info
```

## 验证安装

安装后向 AI 提问：

> 帮我查一下这个 YouTube 博主的信息：https://www.youtube.com/@马克的技术工作坊

如果返回了昵称、简介、头像 URL 和频道主页链接，说明安装成功。

## 更新技能

```bash
cd niche-skills
git pull
```

- 软链接方式：自动同步最新代码
- 复制方式：手动重新复制一次即可

## 卸载技能

删除对应目录即可：

```bash
# 软链接方式
rm ~/.agents/skills/youtube-creator-info

# 复制方式
rm -rf ~/.codex/skills/youtube-creator-info
```

## 故障排查

### "requests 模块未找到"

```bash
pip3 install requests
```

### 访问 YouTube 页面超时或返回异常

- 先确认本机网络可访问 `youtube.com`
- 再检查传入的是否是频道主页、`@handle` 或 `channel id`
- 如果当前网络环境对 YouTube 有限制，脚本可能无法拿到频道页 HTML
