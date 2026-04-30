#!/usr/bin/env python3
"""
为 AI 创作者 / AI 大神生成 Obsidian 风格的个人资料 md 文档。

本脚本不负责拉取 B 站数据，只接收已获取的 JSON（来自 bilibili-up-info 技能）。

用法：
    python3 generate_profile.py --json '{...}' --category "AI 创作者" [--stars 4]
    python3 generate_profile.py --json-file /tmp/up.json --category "AI 创作者" [--stars 4]

依赖：
    Python 3.8+，不需要额外第三方库
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def doc_title_prefix(category: str) -> str:
    """根据分类确定文档标题前缀。"""
    if category in ("两者都是", "AI 大神 + AI 创作者", "AI 大神"):
        return "AI 大神"
    return "AI 创作者"


def output_dir_name(category: str) -> str:
    """根据分类确定输出目录名。"""
    if category in ("两者都是", "AI 大神 + AI 创作者", "AI 大神"):
        return "A_AI-Gurus(AI大神)"
    return "A_AI-Content-Creator(AI创作者)"


def safe_filename_part(value: str) -> str:
    """移除不适合出现在文件名中的字符。"""
    cleaned = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", value).strip(" ._")
    return cleaned or "未命名UP主"


def normalize_stars(stars: int) -> int:
    """星级只允许 1-5，避免生成空星级或异常长度。"""
    if stars < 1 or stars > 5:
        raise ValueError("星级必须是 1-5 的整数")
    return stars


def generate_markdown(
    name: str,
    intro: str,
    avatar_url: str,
    space_url: str,
    mid: str,
    category: str,
    stars: int = 4,
    output: Optional[str] = None,
) -> str:
    """生成 Obsidian 风格的个人资料 md 文档。"""
    now = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S")

    # 确定 tags 和分类
    if category == "两者都是" or category == "AI 大神 + AI 创作者":
        tags = ["AI", "创作者", "大神"]
        classification = "AI 大神 + AI 创作者"
    elif category == "AI 创作者":
        tags = ["AI", "创作者"]
        classification = "AI 创作者"
    elif category == "AI 大神":
        tags = ["AI", "大神"]
        classification = "AI 大神"
    else:
        tags = ["AI"]
        classification = category

    stars_str = "⭐️" * normalize_stars(stars)
    date_str = now

    tags_yaml = "\n".join(f"  - {tag}" for tag in tags)
    md = f"""---
创建日期: {date_str}
tags:
{tags_yaml}
分类:
  - {classification}
星级: {stars_str}
author_url: {avatar_url}
---

### 自我介绍
![{name}|150]({avatar_url})
> {intro}

### 平台
- [**B站**]({space_url})
"""

    if output:
        output_path = Path(output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md, encoding="utf-8")
        print(f"已保存到：{output_path.resolve()}")

    return md


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="为 AI 创作者/大神生成个人资料 md 文档")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--json", help="已获取的 UP 主 JSON 字符串（来自 bilibili-up-info 技能）")
    source.add_argument("--json-file", help="读取已获取的 UP 主 JSON 文件（来自 bilibili-up-info 技能）")
    parser.add_argument("--category", default="AI 创作者", help="分类：AI 大神 / AI 创作者 / 两者都是")
    parser.add_argument("--stars", type=int, default=4, help="星级（1-5），默认 4")
    parser.add_argument("--output", help="输出文件路径，不传则自动生成")
    return parser.parse_args()


def load_profile_json(args: argparse.Namespace) -> dict:
    """从命令行 JSON 字符串或 JSON 文件中读取 UP 主资料。"""
    raw = args.json
    if args.json_file:
        raw = Path(args.json_file).expanduser().read_text(encoding="utf-8")

    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败：{e}") from e


def main() -> int:
    args = parse_args()

    try:
        info = load_profile_json(args)
        normalize_stars(args.stars)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    if not info.get("success"):
        error_json = json.dumps({"success": False, "error": info.get("error", "未知错误")}, ensure_ascii=False)
        print(error_json, file=sys.stderr)
        return 1

    required_fields = ("mid", "name", "intro", "avatar_url", "space_url")
    missing_fields = [field for field in required_fields if field not in info]
    if missing_fields:
        print(f"JSON 缺少必要字段：{', '.join(missing_fields)}", file=sys.stderr)
        return 1

    name = str(info["name"])
    category = args.category
    prefix = doc_title_prefix(category)

    # 自动生成路径：raw/A_AI-Gurus(AI大神)/AI 大神 - 慢学AI.md
    if not args.output:
        sub_dir = output_dir_name(category)
        args.output = f"raw/{sub_dir}/{prefix} - {safe_filename_part(name)}.md"

    generate_markdown(
        name=name,
        intro=info["intro"],
        avatar_url=info["avatar_url"],
        space_url=info["space_url"],
        mid=info["mid"],
        category=category,
        stars=args.stars,
        output=args.output,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
