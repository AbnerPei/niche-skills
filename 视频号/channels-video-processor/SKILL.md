---
name: channels-video-processor
description: >
  获取视频号创作者基础信息，并生成对应的 Obsidian 资料 md。用户提到视频号、
  微信视频号、创作者主页、finder ID、channels.weixin.qq.com 链接、weixin.qq.com/sph
  短链，或想把视频号创作者整理成资料卡时应使用。只要 URL 域名是 weixin.qq.com
  且路径包含 /sph/，就按微信视频号处理。返回昵称、简介、头像 URL、主页链接；如需落盘为 md，
  继续调用 ai-creator-info。
---

# 视频号创作者信息查询

## 概述

本 Skill 对齐 `bilibili-up-info` 的职责边界：
- `fetch_channels_info.py`：只负责查询视频号创作者资料，并输出 JSON
- `process_channels_video.py`：先调用 `fetch_channels_info.py`，再调用 `ai-creator-info` 生成 md

不再下载封面图、不再下载视频、不再转写内容。

## 资源文件

| 文件 | 说明 |
|------|------|
| `scripts/fetch_channels_info.py` | 核心查询脚本，返回创作者基础信息 JSON |
| `scripts/process_channels_video.py` | 桥接脚本：查询后调用 `ai-creator-info` 生成 md |
| `requirements.txt` | Python 依赖声明 |

## 前置条件

- Python 3.8+
- `requests`：`python3 -m pip install -r "{skill_path}/requirements.txt"`
- 若需要生成 md，仓库中需存在 `B站/ai-creator-info/scripts/generate_profile.py`

## 用法

### 1. 只查询基础信息

```bash
python3 {skill_path}/scripts/fetch_channels_info.py \
  "https://channels.weixin.qq.com/finder-preview/pages/sph?id=ANFZXzn3N9"
```

### 2. 查询后直接生成 md

```bash
python3 {skill_path}/scripts/process_channels_video.py \
  "https://channels.weixin.qq.com/finder-preview/pages/sph?id=ANFZXzn3N9" \
  --category "AI 创作者" \
  --stars 4
```

### 3. 复用已有 JSON 生成 md

```bash
python3 {skill_path}/scripts/process_channels_video.py \
  --json-file /tmp/channels_creator.json \
  --category "AI 创作者" \
  --stars 4
```

## 输入

- `finder ID`：例如 `ANFZXzn3N9`
- 视频号页面 URL：例如 `https://channels.weixin.qq.com/finder-preview/pages/sph?id=ANFZXzn3N9`
- 短链 URL：例如 `https://weixin.qq.com/sph/ANFZXzn3N9`
- `weixin.qq.com/sph/...` 一律判断为微信视频号短链，例如 `https://weixin.qq.com/sph/Av0dEnlvVz`

## 输出

### 查询脚本 stdout JSON

```json
{
  "success": true,
  "platform": "视频号",
  "mid": "ANFZXzn3N9",
  "finder_id": "ANFZXzn3N9",
  "name": "创作者昵称",
  "intro": "视频描述/简介",
  "description": "视频描述/简介",
  "avatar_url": "https://wx.qlogo.cn/finderhead/...",
  "space_url": "https://channels.weixin.qq.com/finder-preview/pages/sph?id=ANFZXzn3N9",
  "profile_url": "https://channels.weixin.qq.com/finder-preview/pages/sph?id=ANFZXzn3N9"
}
```

### 生成脚本 stdout JSON

```json
{
  "success": true,
  "meta": {
    "platform": "视频号",
    "finder_id": "ANFZXzn3N9",
    "name": "创作者昵称"
  },
  "note_path": "/path/to/raw/A_AI-Content-Creator(AI创作者)/AI 创作者 - 创作者昵称.md"
}
```

## 工作流程

1. 判断平台并解析用户输入中的 `finder ID`
   - 如果域名是 `weixin.qq.com` 且路径包含 `/sph/`，直接视为微信视频号短链
2. 直接请求视频号公开接口 `/finder-preview/api/feed/get_feed_info`
3. 先把返回 JSON 原样展示给用户确认，字段与 `bilibili-up-info` 兼容：`name`、`intro`、`avatar_url`、`space_url`
4. 如果用户当前语境是在“记录 / 收藏 / 整理 AI 创作者资料”或 AI-Master / Obsidian 资料库中使用，不要停在 JSON；继续询问分类和星级：
   - 分类：`AI 大神`、`AI 创作者`、`两者都是`
   - 星级：`1-5`，默认建议 `4`
5. 拿到分类和星级后，调用 `process_channels_video.py`，把同一份 JSON 传给 `ai-creator-info` 生成 Obsidian md
6. 不重复抓取，不下载封面图、视频或正文内容

## 注意事项

- 本 Skill 只处理“创作者资料”这条链路，不处理视频下载、封面下载、Whisper 转写
- 视频号接口当前可直接通过 `shortUri` 拉基础资料，不再依赖 Playwright
- 生成 md 前必须先询问用户分类和星级，`process_channels_video.py` 不再接受静默默认值
- 如果用户明确只想看基础信息，停在 `fetch_channels_info.py` 的 JSON 即可
- 如果用户给出视频号链接且当前目标是维护 AI 创作者 / AI 大神 Obsidian 资料库，应在展示 JSON 后继续完成 md 创建，不要只做查询
