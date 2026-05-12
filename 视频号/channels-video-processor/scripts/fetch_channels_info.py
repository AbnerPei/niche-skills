#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch basic creator information from a WeChat Channels (视频号) page."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse, parse_qs


API_GET_FEED_INFO = "https://channels.weixin.qq.com/finder-preview/api/feed/get_feed_info"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
PROFILE_URL = "https://channels.weixin.qq.com/finder-preview/pages/sph?id={finder_id}"


class ChannelsFetchError(RuntimeError):
    """Raised when WeChat Channels returns an unusable response."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="抓取视频号创作者基础信息：昵称、简介、头像 URL、主页链接。",
    )
    parser.add_argument(
        "target",
        help="视频号 finder ID，或视频号主页 URL，例如 https://channels.weixin.qq.com/finder-preview/pages/sph?id=ANFZXzn3N9",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=12.0,
        help="请求超时时间，单位秒。默认：12",
    )
    parser.add_argument(
        "--output",
        help="可选。把结果 JSON 写入指定文件；不传则只输出到 stdout。",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON 缩进空格数。默认：2",
    )
    return parser.parse_args()


def extract_finder_id(target: str) -> str:
    """从输入中提取 finder ID。"""
    value = target.strip()
    # 纯 ID
    if re.fullmatch(r"[A-Za-z0-9_\-]{8,}", value):
        return value

    parsed = urlparse(value)
    host = parsed.netloc.lower()

    # 微信视频号短链：只要是 weixin.qq.com/sph/...，就按视频号处理。
    if host == "weixin.qq.com" and "/sph/" in parsed.path:
        short_id = parsed.path.rstrip("/").split("/")[-1]
        if re.fullmatch(r"[A-Za-z0-9_\-]{8,}", short_id):
            return short_id

    # URL 中提取 id 参数
    params = parse_qs(parsed.query)
    if "id" in params:
        return params["id"][0]
    # 尝试从 path 中提取
    match = re.search(r"sph[=/](\w+)", value)
    if match:
        return match.group(1)
    raise SystemExit(f"无法从输入中解析视频号 finder ID：{target}")


def require_requests():
    try:
        import requests

        return requests
    except ImportError as exc:
        raise SystemExit("缺少依赖 requests，请先执行：python3 -m pip install requests") from exc


def create_session():
    requests = require_requests()
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://channels.weixin.qq.com",
            "Referer": "https://channels.weixin.qq.com/",
        }
    )
    return session


def request_json(session, finder_id: str, timeout: float) -> Dict[str, Any]:
    payload = {"baseReq": {"generalToken": ""}, "shortUri": finder_id}
    url = PROFILE_URL.format(finder_id=finder_id)
    response = session.post(API_GET_FEED_INFO, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    err_code = data.get("errCode", -1)
    if err_code != 0:
        raise ChannelsFetchError(data.get("errMsg") or f"视频号接口返回 errCode={err_code}")

    author = data.get("data", {}).get("authorInfo", {}) or {}
    feed = data.get("data", {}).get("feedInfo", {}) or {}
    if not author:
        raise ChannelsFetchError("接口返回成功，但缺少 authorInfo")

    return {
        "success": True,
        "platform": "视频号",
        "mid": finder_id,
        "finder_id": finder_id,
        "name": author.get("nickname", ""),
        "intro": feed.get("description", ""),
        "description": feed.get("description", ""),
        "avatar_url": author.get("headImgUrl", ""),
        "space_url": url,
        "profile_url": url,
    }


def fetch_profile(finder_id: str, timeout: float) -> Dict[str, Any]:
    """通过视频号公开接口获取创作者信息。"""
    session = create_session()
    try:
        return request_json(session, finder_id, timeout)
    except Exception as exc:
        raise ChannelsFetchError(str(exc)) from exc


def write_output(profile: Dict[str, Any], output: Optional[str], indent: int) -> None:
    """输出结果。"""
    text = json.dumps(profile, ensure_ascii=False, indent=indent)
    print(text)
    if output:
        Path(output).expanduser().write_text(text + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    finder_id = extract_finder_id(args.target)

    try:
        profile = fetch_profile(finder_id, args.timeout)
        write_output(profile, args.output, args.indent)
        return 0
    except Exception as exc:
        error_payload = {
            "success": False,
            "mid": finder_id,
            "finder_id": finder_id,
            "error": str(exc),
        }
        print(
            json.dumps(error_payload, ensure_ascii=False, indent=args.indent),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
