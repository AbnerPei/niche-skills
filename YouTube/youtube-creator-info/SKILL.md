---
name: youtube-creator-info
description: >
  获取 YouTube 博主基础信息，并可生成对应的 Obsidian 资料 md。用户提到
  YouTube、YouTube 博主、频道主页、handle、@用户名、channel id、头像、简介，
  或给出 https://www.youtube.com/@...、https://www.youtube.com/channel/... 这类链接时应使用。
  返回昵称、简介、头像 URL、频道主页链接；如需落盘为 md，继续调用 ai-creator-info。
---

# YouTube 博主信息查询

## 概述

本 Skill 对齐现有 `bilibili-up-info` / `channels-video-processor` 的职责边界：
- `fetch_youtube_creator_info.py`：只负责查询 YouTube 博主资料，并输出 JSON
- `process_youtube_creator.py`：先调用查询脚本，再调用 `ai-creator-info` 生成 md

不下载视频，不抓评论，不做字幕转写。

## 资源文件

| 文件 | 说明 |
|------|------|
| `scripts/fetch_youtube_creator_info.py` | 核心查询脚本，返回博主基础信息 JSON |
| `scripts/process_youtube_creator.py` | 桥接脚本：查询后调用 `ai-creator-info` 生成 md |
| `references/examples.md` | 使用示例 |
| `references/install-guide.md` | 安装说明 |
| `requirements.txt` | Python 依赖声明 |

## 前置条件

- Python 3.8+
- `requests`：`python3 -m pip install -r "{skill_path}/requirements.txt"`
- 若需要生成 md，仓库中需存在 `B站/ai-creator-info/scripts/generate_profile.py`

## 用法

### 1. 只查询基础信息

```bash
python3 {skill_path}/scripts/fetch_youtube_creator_info.py \
  "https://www.youtube.com/@GoogleDevelopers"
```

也支持直接传 `@handle`：

```bash
python3 {skill_path}/scripts/fetch_youtube_creator_info.py "@GoogleDevelopers"
```

也支持传 `channel id`：

```bash
python3 {skill_path}/scripts/fetch_youtube_creator_info.py "UC_x5XG1OV2P6uZZ5FSM9Ttw"
```

### 2. 查询后直接生成 md

```bash
python3 {skill_path}/scripts/process_youtube_creator.py \
  "https://www.youtube.com/@GoogleDevelopers" \
  --category "AI 创作者" \
  --stars 4
```

### 3. 复用已有 JSON 生成 md

```bash
python3 {skill_path}/scripts/process_youtube_creator.py \
  --json-file /tmp/youtube_creator.json \
  --category "AI 创作者" \
  --stars 4
```

## 输入

- `@handle`：例如 `@GoogleDevelopers`
- 频道主页 URL：例如 `https://www.youtube.com/@GoogleDevelopers`
- 频道 ID：例如 `UC_x5XG1OV2P6uZZ5FSM9Ttw`
- 传统频道 URL：例如 `https://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw`

## 输出

### 查询脚本 stdout JSON

```json
{
  "success": true,
  "platform": "YouTube",
  "mid": "UC_x5XG1OV2P6uZZ5FSM9Ttw",
  "channel_id": "UC_x5XG1OV2P6uZZ5FSM9Ttw",
  "creator_id": "UC_x5XG1OV2P6uZZ5FSM9Ttw",
  "handle": "@GoogleDevelopers",
  "name": "Google for Developers",
  "intro": "The Google Developers channel...",
  "description": "The Google Developers channel...",
  "avatar_url": "https://yt3.googleusercontent.com/...",
  "space_url": "https://www.youtube.com/@GoogleDevelopers",
  "profile_url": "https://www.youtube.com/@GoogleDevelopers"
}
```

### 生成脚本 stdout JSON

```json
{
  "success": true,
  "meta": {
    "platform": "YouTube",
    "channel_id": "UC_x5XG1OV2P6uZZ5FSM9Ttw",
    "name": "Google for Developers"
  },
  "note_path": "/path/to/A_AI-Content-Creator(AI 创作者)/AI 创作者 - Google for Developers.md"
}
```

## 工作流程

1. 判断用户输入的是 `@handle`、频道 URL 还是 `channel id`
2. 规范化为频道主页 URL
3. 请求 YouTube 频道主页 HTML
4. 从页面元信息和内嵌 JSON 中提取字段：
   - `name`
   - `intro`
   - `avatar_url`
   - `space_url`
   - `channel_id`
   - `handle`
5. 先把返回 JSON 原样展示给用户确认，字段与 `bilibili-up-info` / `channels-video-processor` 兼容
6. 如果用户当前语境是在“记录 / 收藏 / 整理 AI 创作者资料”或 AI-Master / Obsidian 资料库中使用，不要停在 JSON；继续询问分类和星级：
   - 分类：`AI 大神`、`AI 创作者`、`两者都是`
   - 星级：`1-5`，默认建议 `4`
7. 拿到分类和星级后，调用 `process_youtube_creator.py`，把同一份 JSON 传给 `ai-creator-info` 生成 Obsidian md

询问时保持最短交互，优先允许用户直接回复数字：
- `1` = AI 大神
- `2` = AI 创作者
- `3` = 两者都是
- 星级直接回 `1-5`
- 如果用户愿意一次说完，支持 `2,4` 这种两数字输入；如果用户想分开选，也支持先回 `2` 再回 `4`

## 注意事项

- 本 Skill 只处理“博主基础资料”这条链路，不处理视频详情、播放列表、评论、字幕
- 默认依赖公开频道页 HTML，不依赖 YouTube Data API key
- 当前环境如果存在 `AI-Master/raw`，默认优先写入该资料库；否则回退到当前目录 `raw/`
- 生成 md 前必须先询问用户分类和星级，`process_youtube_creator.py` 不再接受静默默认值
- 如果用户明确只想看基础信息，停在 `fetch_youtube_creator_info.py` 的 JSON 即可
- 如果用户给出 YouTube 博主链接且当前目标是维护 AI 创作者 / AI 大神 Obsidian 资料库，应在展示 JSON 后继续完成 md 创建，不要只做查询
