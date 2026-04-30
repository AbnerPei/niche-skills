【UsageGuide】B站-UP主信息查询skill

> [B站-UP主信息查询skill](https://github.com/AbnerPei/niche-skills/tree/master/B站/bilibili-up-info)
>
> 2026-05-01

触发：**B站 UP 主信息、空间主页、mid、头像、简介**

- 通过空间主页查询：

```text
帮我查一下这个 B 站 UP 主的信息：https://space.bilibili.com/163637592
```

- 通过 mid 查询：

```text
帮我看看 B 站 UP 主 546195 的信息
```

- 需要下载头像：

```text
把 B 站 UP 主 163637592 的头像下载下来
```

输出默认是结构化 JSON，包含：

```json
{
  "success": true,
  "mid": "163637592",
  "name": "UP主昵称",
  "intro": "UP主的个人签名/介绍",
  "avatar_url": "https://i0.hdslb.com/bfs/face/xxx.jpg",
  "space_url": "https://space.bilibili.com/163637592"
}
```

如果查询频繁或接口受限，可以提供 B 站 Cookie，或设置 `BILIBILI_COOKIE` 环境变量后再执行。
