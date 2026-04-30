---
name: bilibili-up-info
description: >
  获取 B 站 UP 主基本信息。用户提到 B站、哔哩哔哩、UP 主、空间主页、mid、头像、
  简介、Bilibili，或给出 https://space.bilibili.com/数字 这类链接时应使用。
  返回昵称、签名/介绍、头像 URL、空间主页链接；如果用户只是要查 UP 主基本资料，
  优先使用此技能。不要把它用于视频搜索、评论抓取、弹幕分析等任务。
---

# Bilibili UP 主信息查询

## 概述

本 Skill 通过调用 B 站公开 API，获取指定 UP 主（创作者）的基本信息，包括：
- **昵称**（name）
- **个人介绍/签名**（intro / sign）
- **头像 URL**（avatar_url）
- **空间主页链接**（space_url）

## 资源文件

本 Skill 提供了以下资源，全部位于 Skill 根目录下：

| 文件 | 说明 |
|------|------|
| `scripts/fetch_bilibili_up_info.py` | 核心查询脚本，已捆绑在 Skill 中 |
| `references/examples.md` | 详细的使用示例（6 个场景） |
| `requirements.txt` | Python 依赖声明 |

## 安装指南

本 Skill 来源于开源仓库 [niche-skills](https://github.com/AbnerPei/niche-skills.git)。仓库入口和 Usage Guide 见根目录 `README.md`，详细安装说明见 `references/install-guide.md`。

### 前置条件

- **Python 3.8+**
- **requests 库**：`python3 -m pip install -r "{skill_path}/requirements.txt"` 或 `python3 -m pip install requests`

## 脚本路径

使用以下路径引用脚本（路径中的 `{skill_path}` 请在运行时替换为 Skill 的实际路径）：

```
{skill_path}/scripts/fetch_bilibili_up_info.py
```

## 用法

### 基本查询（无 Cookie）

```bash
python3 {skill_path}/scripts/fetch_bilibili_up_info.py <mid或空间URL>
```

### 携带 Cookie 查询（可获取更完整的数据）

```bash
python3 {skill_path}/scripts/fetch_bilibili_up_info.py <mid或空间URL> --cookie '你的B站Cookie'
```

### 同时下载头像

```bash
python3 {skill_path}/scripts/fetch_bilibili_up_info.py <mid或空间URL> --download-avatar
```

### 可选参数

| 参数 | 说明 |
|------|------|
| `--cookie` | B 站 Cookie 字符串，也可通过 `BILIBILI_COOKIE` 环境变量提供 |
| `--cookie-file` | 读取 Cookie 的文本文件路径，优先级高于 `--cookie` |
| `--download-avatar` | 下载头像文件到本地 |
| `--avatar-dir` | 头像下载目录（默认 `bilibili_avatars`） |
| `--output` | 将结果 JSON 写入指定文件 |
| `--timeout` | 请求超时时间（默认 12 秒） |

## 输入

- **mid**：纯数字的 UP 主 ID（例如 `163637592`）
- **空间主页 URL**：例如 `https://space.bilibili.com/163637592`

## 输出

脚本输出一个 JSON 对象到 stdout，结构如下：

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

如果请求失败，stderr 会输出错误 JSON：
```json
{
  "success": false,
  "mid": "163637592",
  "error": "错误描述"
}
```

## 工作流程

当你接收到用户的查询请求时，按以下步骤执行：

1. **解析输入**：判断用户提供的是 mid（纯数字）还是 B 站空间主页 URL
2. **构造路径**：获取 Skill 的实际路径，替换 `{skill_path}` 为真实路径
3. **构建命令**：使用脚本的完整路径，传入相应的参数
4. **执行脚本**：使用当前环境可用的命令执行工具运行脚本；如果运行环境需要网络权限，按宿主工具的权限流程处理
5. **处理结果**：
   - 默认保留脚本返回的 JSON 结构，便于后续技能继续消费
   - 成功时直接输出脚本返回的 JSON（包含 `name`、`intro`、`avatar_url`、`space_url`）
   - 失败时输出错误 JSON 并给出排查建议（如是否需要 Cookie、mid 是否正确等）
   - 仅在用户明确要求"用表格/文字形式展示"时，再额外补充可读格式

### 展示格式（按优先级）

**1️⃣ 首选：直接输出 JSON**

```json
{
  "success": true,
  "mid": "163637592",
  "name": "老师好我叫何同学",
  "intro": "目标是做有意思的视频｜合作请联系xhaxx1123@163.com",
  "avatar_url": "https://i0.hdslb.com/bfs/face/492d0bb71749332040f9d812954fa0b52e66c490.jpg",
  "space_url": "https://space.bilibili.com/163637592"
}
```

**2️⃣ 仅当用户要求可读格式时**，再转为表格展示：

```
## 老师好我叫何同学

| 字段 | 内容 |
|------|------|
| UP 主 ID | 163637592 |
| 个人简介 | 目标是做有意思的视频... |
| 头像 | [点击查看](头像URL) |
| 空间主页 | [链接](space_url) |
```

## 参考示例

详细的完整示例（包括输入、命令、输出、展示格式）请参见 `references/examples.md`，覆盖了以下 6 个场景：

1. 通过空间 URL 查询
2. 通过纯数字 mid 查询
3. 查询并下载头像
4. 携带 Cookie 查询
5. 将结果保存到文件
6. 查询失败的情况

## 注意事项

- 无水印情况下无需 Cookie 也能查询，但某些 UP 主或高频率查询可能需要提供 Cookie
- Cookie 可以通过 `--cookie` 参数或 `BILIBILI_COOKIE` 环境变量传入
- 脚本内置了 WBI 签名机制，会自动处理 B 站接口的签名要求
- 如果 WBI 接口失败，脚本会自动回退到旧版接口和 card 接口
- 如果用户给出了完整的空间 URL（如 `https://space.bilibili.com/12345`），脚本可以直接解析，无需手动提取 mid
- 首次使用前请确保安装了 `requests` 依赖
- 若用户后续要把 AI 相关 UP 主沉淀成 Obsidian 资料文档，继续调用 `ai-creator-info`，并把本技能返回的 JSON 原样传给它
