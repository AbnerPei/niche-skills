# AI 创作者 / AI 大神 - 使用示例

## 示例 1：AI 创作者（完整流程）

**用户输入：**
> 记录一下这个 B 站的 AI 创作者 https://space.bilibili.com/28321599

**Step 1 - 调用 bilibili-up-info 查询：**
```bash
# 使用 bilibili-up-info 技能获取 JSON
python3 {bilibili-up-info路径}/scripts/fetch_bilibili_up_info.py 28321599
```

**返回 JSON：**
```json
{
  "success": true,
  "mid": "28321599",
  "name": "慢学AI",
  "intro": "我是一名正在转型AI的产品经理，也是一个"慢学主义"的信徒。",
  "avatar_url": "https://i0.hdslb.com/bfs/face/eff22de48bce3370bdca5545370c7773d57199d7.jpg",
  "space_url": "https://space.bilibili.com/28321599"
}
```

**Step 2 - 询问分类：**
> 这是 AI 大神、AI 创作者，还是两者都是？请选择。
> - AI 大神
> - AI 创作者  ← 用户选择
> - 两者都是

**Step 3 - 询问星级：**
> 请为这位 UP 主评分：
> - 1 ⭐️
> - 2 ⭐️⭐️
> - 3 ⭐️⭐️⭐️
> - 4 ⭐️⭐️⭐️⭐️  ← 用户选择
> - 5 ⭐️⭐️⭐️⭐️⭐️

**Step 4 - 生成 md（直接使用已有 JSON）：**
```bash
# 无需再次拉取，直接将 JSON 传给 generate_profile.py
python3 {ai-creator-info路径}/scripts/generate_profile.py \
  --json '{"success":true,"mid":"28321599","name":"慢学AI","intro":"我是一名正在转型AI的产品经理，也是一个\"慢学主义\"的信徒。","avatar_url":"https://i0.hdslb.com/bfs/face/eff22de48bce3370bdca5545370c7773d57199d7.jpg","space_url":"https://space.bilibili.com/28321599"}' \
  --category "AI 创作者" \
  --stars 4
```

**自动生成的 md 文档（保存到 `raw/A_AI-Content-Creator(AI创作者)/AI 创作者 - 慢学AI.md`）：**
```markdown
---
创建日期: 2026-05-01T01:55:00
tags:
  - AI
  - 创作者
分类:
  - AI 创作者
星级: ⭐️⭐️⭐️⭐️
author_url: https://i0.hdslb.com/bfs/face/eff22de48bce3370bdca5545370c7773d57199d7.jpg
---

### 自我介绍
![慢学AI|150](https://i0.hdslb.com/bfs/face/eff22de48bce3370bdca5545370c7773d57199d7.jpg)
> 我是一名正在转型AI的产品经理，也是一个"慢学主义"的信徒。

### 平台
- [**B站**](https://space.bilibili.com/28321599)
```

---

## 示例 2：AI 大神

**用户输入：**
> 记录这个 AI 大神，B站 mid 是 163637592

**Step 1 - 查询：**
```bash
python3 {bilibili-up-info路径}/scripts/fetch_bilibili_up_info.py 163637592
```

**Step 2 - 用户选择分类：** AI 大神

**Step 3 - 用户选择星级：** 5 ⭐️⭐️⭐️⭐️⭐️

**Step 4 - 生成：**
```bash
python3 {ai-creator-info路径}/scripts/generate_profile.py \
  --json '{"success":true,"mid":"163637592","name":"老师好我叫何同学",...}' \
  --category "AI 大神" --stars 5
```

自动保存到：`raw/A_AI-Gurus(AI大神)/AI 大神 - 老师好我叫何同学.md`

生成的 tags：`AI`, `大神`，分类为 `AI 大神`

---

## 示例 3：两者都是

**Step 2 - 用户选择分类：** 两者都是

**Step 4 - 生成：**
```bash
python3 {ai-creator-info路径}/scripts/generate_profile.py \
  --json '{...}' \
  --category "两者都是" --stars 4
```

自动保存到：`raw/A_AI-Gurus(AI大神)/AI 大神 - {UP主名}.md`

生成的 tags：`AI`, `创作者`, `大神`，分类为 `AI 大神 + AI 创作者`
