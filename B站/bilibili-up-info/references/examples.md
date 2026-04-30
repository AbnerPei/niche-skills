# Bilibili UP 主信息查询 - 使用示例

本文档提供了该 Skill 在各个场景下的完整使用示例，包括输入、命令和预期输出。

---

## 示例 1：通过空间 URL 查询

**用户输入：**
> 帮我查一下这个 B 站 UP 主的信息：https://space.bilibili.com/163637592

**执行的命令：**
```bash
python3 scripts/fetch_bilibili_up_info.py https://space.bilibili.com/163637592
```

**预期输出：**
```json
{
  "success": true,
  "mid": "163637592",
  "name": "老师好我叫何同学",
  "intro": "目标是做有意思的视频｜合作请联系xhaxx1123@163.com｜粉丝想做htxcontact@163.com 请留下vx或者手机号",
  "avatar_url": "https://i0.hdslb.com/bfs/face/492d0bb71749332040f9d812954fa0b52e66c490.jpg",
  "space_url": "https://space.bilibili.com/163637592"
}
```

**对用户的展示格式：**
> ## 老师好我叫何同学
> **UP 主 ID：** 163637592
> **个人简介：** 目标是做有意思的视频｜合作请联系xhaxx1123@163.com｜粉丝想做htxcontact@163.com 请留下vx或者手机号
> **头像：** [点击查看](https://i0.hdslb.com/bfs/face/492d0bb71749332040f9d812954fa0b52e66c490.jpg)
> **空间主页：** [https://space.bilibili.com/163637592](https://space.bilibili.com/163637592)

---

## 示例 2：通过纯数字 mid 查询

**用户输入：**
> 帮我看看 B 站 UP 主 546195 的信息

**执行的命令：**
```bash
python3 scripts/fetch_bilibili_up_info.py 546195
```

**预期输出：**
```json
{
  "success": true,
  "mid": "546195",
  "name": "老番茄",
  "intro": "新浪微博：_老番茄_",
  "avatar_url": "https://i0.hdslb.com/bfs/face/xxx.jpg",
  "space_url": "https://space.bilibili.com/546195"
}
```

---

## 示例 3：查询并下载头像

**用户输入：**
> 把 B 站 UP 主 163637592 的头像下载下来

**执行的命令：**
```bash
python3 scripts/fetch_bilibili_up_info.py 163637592 --download-avatar --avatar-dir ./avatars
```

**预期输出：**
```json
{
  "success": true,
  "mid": "163637592",
  "name": "老师好我叫何同学",
  "intro": "目标是做有意思的视频...",
  "avatar_url": "https://i0.hdslb.com/bfs/face/492d0bb71749332040f9d812954fa0b52e66c490.jpg",
  "space_url": "https://space.bilibili.com/163637592",
  "avatar_path": "/current/working/dir/avatars/163637592_老师好我叫何同学.jpg"
}
```

---

## 示例 4：携带 Cookie 查询（高频或受限场景）

**执行的命令：**
```bash
python3 scripts/fetch_bilibili_up_info.py 163637592 --cookie "SESSDATA=xxx; bili_jct=xxx"
```

如果用户提供了 Cookie 字符串但不想在命令中暴露，可以改用环境变量：
```bash
export BILIBILI_COOKIE="SESSDATA=xxx; bili_jct=xxx"
python3 scripts/fetch_bilibili_up_info.py 163637592
```

---

## 示例 5：将结果保存到文件

**执行的命令：**
```bash
python3 scripts/fetch_bilibili_up_info.py 163637592 --output ./result.json
```

---

## 示例 6：查询失败的情况

**执行的命令：**
```bash
python3 scripts/fetch_bilibili_up_info.py 000000
```

**预期输出（stderr）：**
```json
{
  "success": false,
  "mid": "000000",
  "error": "WBI 接口失败：B 站接口返回失败 code=-404, message=啥都木有"
}
```

**对用户的展示格式：**
> 查询失败，错误信息：B 站接口返回失败（-404），未找到该 UP 主。
> 建议：请检查 mid 或 URL 是否正确。如果确认无误，可以尝试提供 B 站 Cookie 后再试。
