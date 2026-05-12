#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视频号创作者资料处理：获取基础信息 JSON，并调用 ai-creator-info 生成 md。"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="视频号创作者资料处理：获取基础信息 → 调用 ai-creator-info 生成 Obsidian md",
    )
    parser.add_argument("target", nargs="?", help="视频号分享链接或 finder ID")
    parser.add_argument("--json-file", help="已有创作者 JSON 文件路径（跳过抓取步骤）")
    parser.add_argument("--category", required=True, help="分类：AI 大神 / AI 创作者 / 两者都是")
    parser.add_argument("--stars", required=True, type=int, help="星级（1-5）")
    parser.add_argument("--output", help="输出 md 路径，不传则按 ai-creator-info 规则自动生成")
    parser.add_argument("--timeout", type=float, default=12.0, help="视频号接口超时秒数")
    return parser.parse_args()


def load_module(module_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块：{module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def fetcher_module():
    return load_module(skill_root() / "scripts" / "fetch_channels_info.py", "fetch_channels_info")


def profile_generator_module():
    module_path = repo_root() / "B站" / "ai-creator-info" / "scripts" / "generate_profile.py"
    return load_module(module_path, "generate_profile")


def load_profile_json(json_file: str) -> Dict[str, Any]:
    return json.loads(Path(json_file).expanduser().read_text(encoding="utf-8"))


def resolve_output_path(generator, category: str, name: str, output: str | None) -> Path:
    if output:
        return Path(output).expanduser()

    if hasattr(generator, "default_output_path"):
        return Path(generator.default_output_path(category, name))

    sub_dir = generator.output_dir_name(category)
    prefix = generator.doc_title_prefix(category)
    filename = f"{prefix} - {generator.safe_filename_part(name)}.md"
    return Path("raw") / sub_dir / filename


def main() -> int:
    args = parse_args()
    fetcher = fetcher_module()
    generator = profile_generator_module()

    if args.json_file:
        info = load_profile_json(args.json_file)
        print(f"✓ 从文件加载创作者信息：{info.get('name', '?')}", file=sys.stderr)
    elif args.target:
        finder_id = fetcher.extract_finder_id(args.target)
        print("正在请求视频号接口，获取创作者信息...", file=sys.stderr)
        info = fetcher.fetch_profile(finder_id, args.timeout)
        print(f"✓ 创作者信息获取成功：{info.get('name', '?')}", file=sys.stderr)
    else:
        print("请提供视频号链接、finder ID，或使用 --json-file", file=sys.stderr)
        return 1

    if not info.get("success"):
        print(json.dumps(info, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    output_path = resolve_output_path(generator, args.category, str(info.get("name", "")), args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generator.generate_markdown(
        name=str(info["name"]),
        intro=str(info.get("intro", "")),
        avatar_url=str(info.get("avatar_url", "")),
        space_url=str(info.get("space_url") or info.get("profile_url", "")),
        mid=str(info.get("mid") or info.get("finder_id", "")),
        category=args.category,
        stars=args.stars,
        output=str(output_path),
        platform_name=str(info.get("platform", "视频号")),
        creator_id=str(info.get("finder_id") or info.get("mid", "")),
        announce_save=False,
    )

    result = {
        "success": True,
        "meta": info,
        "note_path": str(output_path.resolve()),
    }
    print(f"✓ 创作者资料 md 已生成：{output_path.resolve()}", file=sys.stderr)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
