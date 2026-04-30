【UsageGuide】B站-AI创作者资料生成skill

> [B站-AI创作者资料生成skill](https://github.com/AbnerPei/niche-skills/tree/master/B站/ai-creator-info)
>
> 2026-05-01

触发：**记录 AI 创作者、收藏 AI 大神、整理 B站 AI UP 主资料**

- 记录一个 AI 创作者：

```text
记录一下这个 B 站的 AI 创作者：https://space.bilibili.com/28321599
```

- 记录一个 AI 大神：

```text
记一下这个 AI 大神，B站 mid 是 163637592
```

执行流程：

1. 先调用 `bilibili-up-info` 查询 UP 主基础 JSON。
2. 询问分类：`AI 大神`、`AI 创作者`、`两者都是`。
3. 询问星级：1-5 星，用户没说时默认 4 星。
4. 把查询到的 JSON 传给 `ai-creator-info/scripts/generate_profile.py` 生成 md。

默认保存路径：

| 分类 | 保存位置 |
|------|----------|
| AI 创作者 | `raw/A_AI-Content-Creator(AI创作者)/AI 创作者 - {UP主名}.md` |
| AI 大神 | `raw/A_AI-Gurus(AI大神)/AI 大神 - {UP主名}.md` |
| 两者都是 | `raw/A_AI-Gurus(AI大神)/AI 大神 - {UP主名}.md` |

生成的 md 适合放入 Obsidian，包含 frontmatter、头像、自我介绍和 B 站主页链接。
