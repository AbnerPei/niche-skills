---
name: ai-creator-info
description: >
  为 AI 创作者 / AI 大神生成 Obsidian 风格个人资料 md。用户提到记录、收藏、
  整理、记一下某个 B 站 AI UP 主、AI 创作者、AI 大神、AI 博主、人工智能博主时应使用。
  本技能先复用 bilibili-up-info 获取 UP 主 JSON，再询问分类和星级，最后落盘为结构化 md。
  如果用户只是查询 UP 主基础资料，应改用 bilibili-up-info。
---

# AI 创作者 / AI 大神 - 个人资料生成

## 概述

本 Skill 依赖 **bilibili-up-info** 技能获取 UP 主原始数据，再加工为结构化的 Obsidian 风格 md 文档。

```
用户输入 mid/URL
        │
        ▼
bilibili-up-info skill    ← 先查询（另一个技能）
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
- 已安装并可调用 `bilibili-up-info` 技能
- 本技能生成 md 不需要额外第三方依赖；保留 `requirements.txt` 只是为了安装流程一致

## 工作流程

### Step 1：调用 bilibili-up-info 查询 UP 主信息

先使用 **bilibili-up-info** 技能，调用它的脚本获取 UP 主 JSON：

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

### Step 4：询问星级

```
请为这位 UP 主评分（输入 1-5 的数字）：
1 ⭐️
2 ⭐️⭐️
3 ⭐️⭐️⭐️
4 ⭐️⭐️⭐️⭐️
5 ⭐️⭐️⭐️⭐️⭐️
```

如果用户没有明确给出星级，默认用 4 星。

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
---

### 自我介绍
![{name}|150]({avatar_url})
> {intro}

### 平台
- [**B站**]({space_url})
```

### Step 6：保存文件

**存放路径：** `当前文件夹/raw/{分类子目录}/`

| 分类 | 保存路径 |
|------|---------|
| AI 创作者 | `raw/A_AI-Content-Creator(AI创作者)/AI 创作者 - {UP主名}.md` |
| AI 大神 | `raw/A_AI-Gurus(AI大神)/AI 大神 - {UP主名}.md` |
| 两者都是 | `raw/A_AI-Gurus(AI大神)/AI 大神 - {UP主名}.md` |

## 与 bilibili-up-info 的分工

- `bilibili-up-info`：只负责查询 UP 主资料，并输出结构化 JSON
- `ai-creator-info`：只负责把已获得的 JSON 加工成资料 md，必要时先调用 `bilibili-up-info`
- 不要在生成资料时重复拉取同一个 UP 主；已经有 JSON 时应直接传给 `generate_profile.py`

## 注意事项

- 本 Skill **不直接拉取 B 站数据**，依赖 `bilibili-up-info` 技能提供 JSON
- 如果用户只想知道 UP 主基本信息，应使用 `bilibili-up-info` 技能而不是本技能
- `generate_profile.py` 接受 `--json` 或 `--json-file`，但不接受 mid/URL
- 保存路径建议询问用户，默认在 `raw/` 下
