# YouTube 博主信息查询 - 使用示例

本文档提供了该 Skill 在常见场景下的完整使用示例，包括输入、命令和预期输出。

---

## 示例 1：通过频道主页 URL 查询

**用户输入：**
> 帮我查一下这个 YouTube 博主的信息：https://www.youtube.com/@马克的技术工作坊

**执行的命令：**
```bash
python3 scripts/fetch_youtube_creator_info.py https://www.youtube.com/@马克的技术工作坊
```

**预期输出：**
```json
{
  "success": true,
  "platform": "YouTube",
  "mid": "频道ID",
  "channel_id": "频道ID",
  "creator_id": "频道ID",
  "handle": "@马克的技术工作坊",
  "name": "博主昵称",
  "intro": "博主简介",
  "description": "博主简介",
  "avatar_url": "https://yt3.googleusercontent.com/xxx",
  "space_url": "https://www.youtube.com/@马克的技术工作坊",
  "profile_url": "https://www.youtube.com/@马克的技术工作坊"
}
```

**对用户的展示格式：**
> ## 博主昵称
> **平台：** YouTube
> **频道 ID：** 频道ID
> **简介：** 博主简介
> **头像：** [点击查看](https://yt3.googleusercontent.com/xxx)
> **主页：** [https://www.youtube.com/@马克的技术工作坊](https://www.youtube.com/@马克的技术工作坊)

---

## 示例 2：通过 `@handle` 查询

**用户输入：**
> 查一下 YouTube 博主 @GoogleDevelopers

**执行的命令：**
```bash
python3 scripts/fetch_youtube_creator_info.py @GoogleDevelopers
```

**预期输出：**
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

---

## 示例 3：通过 `channel id` 查询

**用户输入：**
> 帮我看看这个 YouTube 频道的信息：UC_x5XG1OV2P6uZZ5FSM9Ttw

**执行的命令：**
```bash
python3 scripts/fetch_youtube_creator_info.py UC_x5XG1OV2P6uZZ5FSM9Ttw
```

---

## 示例 4：查询后直接生成 md

**执行的命令：**
```bash
python3 scripts/process_youtube_creator.py \
  "https://www.youtube.com/@GoogleDevelopers" \
  --category "AI 创作者" \
  --stars 4
```

**预期输出：**
```json
{
  "success": true,
  "meta": {
    "success": true,
    "platform": "YouTube",
    "channel_id": "UC_x5XG1OV2P6uZZ5FSM9Ttw",
    "name": "Google for Developers"
  },
  "note_path": "/current/working/dir/raw/A_AI-Content-Creator(AI创作者)/AI 创作者 - Google for Developers.md"
}
```

---

## 示例 5：将结果保存到文件

**执行的命令：**
```bash
python3 scripts/fetch_youtube_creator_info.py @GoogleDevelopers --output ./result.json
```

---

## 示例 6：查询失败的情况

**执行的命令：**
```bash
python3 scripts/fetch_youtube_creator_info.py https://www.youtube.com/@does-not-exist
```

**预期输出（stderr）：**
```json
{
  "success": false,
  "source": "https://www.youtube.com/@does-not-exist",
  "error": "未能从页面中解析出有效的 YouTube 博主信息"
}
```

**对用户的展示格式：**
> 查询失败，错误信息：未能从页面中解析出有效的 YouTube 博主信息。
> 建议：请检查频道 URL / handle / channel id 是否正确，或稍后再试。
