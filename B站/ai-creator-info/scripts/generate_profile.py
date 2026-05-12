#!/usr/bin/env python3
"""
为 AI 创作者 / AI 大神生成 Obsidian 风格的个人资料 md 文档。

本脚本不负责拉取平台数据，只接收已获取的 JSON（来自 bilibili-up-info、
视频号创作者信息脚本等）并转成统一 md。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


DEFAULT_AI_MASTER_RAW_DIR = Path("/Users/peijianbo/Documents/MeMe/AI-Master/raw")


def doc_title_prefix(category: str) -> str:
    """根据分类确定文档标题前缀。"""
    if category in ("两者都是", "AI 大神 + AI 创作者", "AI 大神"):
        return "AI 大神"
    return "AI 创作者"


def output_dir_name(category: str) -> str:
    """根据分类确定输出目录名。"""
    if category in ("两者都是", "AI 大神 + AI 创作者", "AI 大神"):
        return "A_AI-Gurus(AI大神)"
    return "A_AI-Content-Creator(AI 创作者)"


def default_output_root() -> Path:
    """优先复用 AI-Master 资料库；没有时再回退到当前目录 raw。"""
    env_value = os.environ.get("AI_CREATOR_INFO_OUTPUT_ROOT", "").strip()
    if env_value:
        return Path(env_value).expanduser()
    if DEFAULT_AI_MASTER_RAW_DIR.exists():
        return DEFAULT_AI_MASTER_RAW_DIR
    return Path("raw")


def default_output_path(category: str, name: str) -> Path:
    """生成默认输出路径。"""
    prefix = doc_title_prefix(category)
    filename = f"{prefix} - {safe_filename_part(name)}.md"
    return default_output_root() / output_dir_name(category) / filename


def safe_filename_part(value: str) -> str:
    """移除不适合出现在文件名中的字符。"""
    cleaned = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", value).strip(" ._")
    return cleaned or "未命名创作者"


def normalize_stars(stars: int) -> int:
    """星级只允许 1-5，避免生成空星级或异常长度。"""
    if stars < 1 or stars > 5:
        raise ValueError("星级必须是 1-5 的整数")
    return stars


def normalize_platform_name(platform_name: str) -> str:
    value = platform_name.strip() or "B站"
    return value


def generate_markdown(
    name: str,
    intro: str,
    avatar_url: str,
    space_url: str,
    mid: str,
    category: str,
    stars: int = 4,
    output: Optional[str] = None,
    platform_name: str = "B站",
    creator_id: str = "",
    announce_save: bool = True,
) -> str:
    """生成 Obsidian 风格的个人资料 md 文档。"""
    now = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S")
    platform_name = normalize_platform_name(platform_name)
    creator_id = creator_id or mid

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
    tags_yaml = "\n".join(f"  - {tag}" for tag in tags)

    platform_meta = [f"平台: {platform_name}"]
    if creator_id:
        platform_meta.append(f"平台ID: {creator_id}")

    md = f"""---
创建日期: {now}
tags:
{tags_yaml}
分类:
  - {classification}
星级: {stars_str}
author_url: {avatar_url}
{chr(10).join(platform_meta)}
---

### 自我介绍
![{name}|150]({avatar_url})
> {intro}

### 平台
- [**{platform_name}**]({space_url})
"""

    if output:
        output_path = Path(output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md, encoding="utf-8")
        if announce_save:
            print(f"已保存到：{output_path.resolve()}")

    return md


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="为 AI 创作者/大神生成个人资料 md 文档")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--json", help="已获取的创作者 JSON 字符串")
    source.add_argument("--json-file", help="读取已获取的创作者 JSON 文件")
    parser.add_argument("--category", required=True, help="分类：AI 大神 / AI 创作者 / 两者都是")
    parser.add_argument("--stars", required=True, type=int, help="星级（1-5）")
    parser.add_argument("--output", help="输出文件路径，不传则自动生成")
    return parser.parse_args()


def load_profile_json(args: argparse.Namespace) -> dict:
    """从命令行 JSON 字符串或 JSON 文件中读取创作者资料。"""
    raw = args.json
    if args.json_file:
        raw = Path(args.json_file).expanduser().read_text(encoding="utf-8")

    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败：{e}") from e


def resolve_profile_url(info: dict) -> str:
    return str(info.get("space_url") or info.get("profile_url") or "")


def resolve_creator_id(info: dict) -> str:
    return str(info.get("mid") or info.get("finder_id") or info.get("creator_id") or "")


def resolve_platform_name(info: dict) -> str:
    return normalize_platform_name(str(info.get("platform") or "B站"))


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

    required_fields = ("name", "intro", "avatar_url")
    missing_fields = [field for field in required_fields if field not in info]
    creator_id = resolve_creator_id(info)
    profile_url = resolve_profile_url(info)
    if not creator_id:
        missing_fields.append("mid/finder_id")
    if not profile_url:
        missing_fields.append("space_url/profile_url")
    if missing_fields:
        print(f"JSON 缺少必要字段：{', '.join(missing_fields)}", file=sys.stderr)
        return 1

    name = str(info["name"])
    category = args.category
    prefix = doc_title_prefix(category)

    if not args.output:
        args.output = str(default_output_path(category, name))

    generate_markdown(
        name=name,
        intro=str(info["intro"]),
        avatar_url=str(info["avatar_url"]),
        space_url=profile_url,
        mid=creator_id,
        category=category,
        stars=args.stars,
        output=args.output,
        platform_name=resolve_platform_name(info),
        creator_id=creator_id,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
