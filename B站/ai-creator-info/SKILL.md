---
name: ai-creator-info
description: >
  为 AI 创作者 / AI 大神生成 Obsidian 风格个人资料 md。用户提到记录、收藏、
  整理某个 AI 创作者、AI 大神、AI 博主、人工智能博主时应使用。
  本技能接收上游资料 JSON（如 bilibili-up-info 或视频号创作者信息脚本），
  再询问分类和星级，最后落盘为结构化 md。如果用户只是查询基础资料，
  应改用对应的平台查询技能。
---

# AI 创作者 / AI 大神 - 个人资料生成

## 概述

本 Skill 依赖上游查询技能获取原始数据，再加工为结构化的 Obsidian 风格 md 文档。

```
用户输入平台主页URL/ID
        │
        ▼
平台查询 skill           ← 先查询（例如 bilibili-up-info / 视频号脚本）
        │
        ▼ 返回 JSON
ai-creator-info skill     ← 再加工（本技能）
        │
        ▼ 生成 md 文档
保存到 raw/{分类子目录}/
```

## 资源文件

| 文件 | 说明 |
|------|------|
| `scripts/generate_profile.py` | 生成 md 文档的核心脚本（接收 JSON，不拉取数据） |
| `references/examples.md` | 完整使用示例 |
| `requirements.txt` | Python 依赖 |

## 前置条件

- Python 3.8+
- 已安装并可调用上游资料查询技能（如 `bilibili-up-info`）
- 本技能生成 md 不需要额外第三方依赖；保留 `requirements.txt` 只是为了安装流程一致

## 工作流程

### Step 1：调用上游查询技能拿到创作者 JSON

例如先使用 **bilibili-up-info** 查询 B 站 UP 主：

```bash
python3 {bilibili-up-info 的路径}/scripts/fetch_bilibili_up_info.py <mid或URL>
```

### Step 2：输出 JSON

**直接输出脚本返回的 JSON**，让用户看到原始数据：

```json
{
  "success": true,
  "mid": "28321599",
  "name": "慢学AI",
  "intro": "我是一名正在转型AI的产品经理...",
  "avatar_url": "https://i0.hdslb.com/bfs/face/eff22de48bce3370bdca5545370c7773d57199d7.jpg",
  "space_url": "https://space.bilibili.com/28321599"
}
```

### Step 3：询问分类

向用户提出分类问题，给出 2-3 个可选项。根据当前工具集选择合适的方式：

```
这是 AI 大神、AI 创作者，还是两者都是？请直接回复：
1. AI 大神
2. AI 创作者
3. 两者都是
```

如果当前宿主提供结构化提问工具，可用同样的 3 个选项发起单选问题；否则直接用上面的文本问题。

优先使用紧凑交互，不要要求用户重复输入完整中文。可接受两种方式：

- 一次回两个数字：例如 `2,4`，前一个表示分类，后一个表示星级
- 分两次回数字：先回 `2`，再回 `4`

### Step 4：询问星级

```
请为这位 UP 主评分（输入 1-5 的数字）：
1 ⭐️
2 ⭐️⭐️
3 ⭐️⭐️⭐️
4 ⭐️⭐️⭐️⭐️
5 ⭐️⭐️⭐️⭐️⭐️
```

如果用户没有明确给出星级，不要擅自使用默认值，继续追问直到拿到明确输入。

### Step 5：生成 md 文档

**此时你已经从 Step 1 获得了 JSON，直接传入 `generate_profile.py`，不要再次拉取。**

```bash
# 将 Step 1 得到的 JSON 直接传给生成脚本
python3 {skill_path}/scripts/generate_profile.py \
  --json '{JSON字符串}' \
  --category "<分类>" \
  --stars N
```

你也可以直接将 JSON 写入临时文件后再传：
```bash
printf '%s\n' '{JSON}' > /tmp/up.json
python3 {skill_path}/scripts/generate_profile.py --json-file /tmp/up.json --category "..." --stars N
```

脚本会自动：
- 根据分类创建 `raw/` 下的对应子目录
- 按命名规则生成文件名
- 保存 md 文档

**你也可以不用脚本，直接按照以下格式编写 md 内容并保存。**

### md 文档格式

| 分类 | tags | 分类 |
|------|------|------|
| AI 创作者 | `AI`, `创作者` | `AI 创作者` |
| AI 大神 | `AI`, `大神` | `AI 大神` |
| 两者都是 | `AI`, `创作者`, `大神` | `AI 大神 + AI 创作者` |

```markdown
---
创建日期: {当前本地时间 ISO 8601}
tags:
  - AI
  - 创作者
分类:
  - {分类}
星级: ⭐️⭐️⭐️⭐️
author_url: {avatar_url}
平台: {platform}
平台ID: {平台用户ID}
---

### 自我介绍
![{name}|150]({avatar_url})
> {intro}

### 平台
- [**{platform}**]({space_url})
```

### Step 6：保存文件

**存放路径：**

- 当前环境如果存在 `/Users/peijianbo/Documents/MeMe/AI-Master/raw`，优先保存到该资料库
- 否则回退到 `当前文件夹/raw/{分类子目录}/`

| 分类 | 保存路径 |
|------|---------|
| AI 创作者 | `A_AI-Content-Creator(AI 创作者)/AI 创作者 - {UP主名}.md` |
| AI 大神 | `raw/A_AI-Gurus(AI大神)/AI 大神 - {UP主名}.md` |
| 两者都是 | `raw/A_AI-Gurus(AI大神)/AI 大神 - {UP主名}.md` |

## 与上游查询技能的分工

- 上游查询技能：只负责查询创作者资料，并输出结构化 JSON
- `ai-creator-info`：只负责把已获得的 JSON 加工成资料 md
- 不要在生成资料时重复拉取；已经有 JSON 时应直接传给 `generate_profile.py`

## 注意事项

- 本 Skill **不直接拉取平台数据**，依赖上游查询技能提供 JSON
- 如果用户只想知道创作者基本信息，应使用对应平台的查询技能而不是本技能
- `generate_profile.py` 接受 `--json` 或 `--json-file`，但不接受 mid/URL
- 生成前必须先拿到用户明确给出的分类和星级，不要静默使用默认值
- 保存路径建议询问用户，默认在 `raw/` 下
