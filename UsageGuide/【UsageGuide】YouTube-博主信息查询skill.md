【UsageGuide】YouTube-博主信息查询skill

> [YouTube-博主信息查询skill](https://github.com/AbnerPei/niche-skills/tree/master/YouTube/youtube-creator-info)
>
> 2026-05-12

触发：**YouTube 博主信息、频道主页、@handle、channel id、头像、简介**

- 通过频道主页查询：

```text
帮我查一下这个 YouTube 博主的信息：https://www.youtube.com/@马克的技术工作坊
```

- 通过 `@handle` 查询：

```text
查一下 YouTube 博主 @GoogleDevelopers
```

- 通过 `channel id` 查询：

```text
帮我看看这个 YouTube 频道的信息：UC_x5XG1OV2P6uZZ5FSM9Ttw
```

输出默认是结构化 JSON，包含：

```json
{
  "success": true,
  "platform": "YouTube",
  "mid": "频道ID",
  "channel_id": "频道ID",
  "creator_id": "频道ID",
  "handle": "@博主handle",
  "name": "博主昵称",
  "intro": "博主简介",
  "avatar_url": "https://yt3.googleusercontent.com/xxx",
  "space_url": "https://www.youtube.com/@博主handle"
}
```

如果当前目标是沉淀 AI 创作者资料，可以继续调用 `process_youtube_creator.py`，再配合 `ai-creator-info` 生成 md。

默认保存位置和之前的 B 站链路一致：
- 当前环境优先保存到 `/Users/peijianbo/Documents/MeMe/AI-Master/raw/...`
- 如果该目录不存在，再回退到当前目录 `raw/...`

交互尽量简短：
- 分类可回 `1/2/3`
- 星级可回 `1-5`
- 也支持一次回两个数字，例如 `2,4`
