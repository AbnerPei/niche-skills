#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch basic creator information from a YouTube channel page."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.parse import unquote, urlparse


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
CHANNEL_ID_RE = re.compile(r"UC[\w-]{20,}")
HANDLE_RE = re.compile(r"@[A-Za-z0-9._-]{2,}")
DISALLOWED_PATH_PREFIXES = (
    "/watch",
    "/playlist",
    "/results",
    "/feed",
    "/shorts",
    "/live",
)


class YouTubeFetchError(RuntimeError):
    """Raised when YouTube returns an unusable response."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="抓取 YouTube 博主基础信息：昵称、简介、头像 URL、频道主页链接。",
    )
    parser.add_argument(
        "target",
        help="YouTube 频道主页 URL、@handle，或 channel id，例如 https://www.youtube.com/@GoogleDevelopers",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="请求超时时间，单位秒。默认：15",
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
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
    )
    return session


def normalize_target(target: str) -> str:
    value = target.strip()
    if not value:
        raise SystemExit("请输入有效的 YouTube 频道主页 URL、@handle 或 channel id")

    if HANDLE_RE.fullmatch(value):
        return f"https://www.youtube.com/{value}"

    if CHANNEL_ID_RE.fullmatch(value):
        return f"https://www.youtube.com/channel/{value}"

    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        host = parsed.netloc.lower()
        if host not in YOUTUBE_HOSTS:
            raise SystemExit(f"不支持的域名：{parsed.netloc}")
        if parsed.path.startswith(DISALLOWED_PATH_PREFIXES):
            raise SystemExit("当前只支持 YouTube 频道主页，不支持视频、播放列表或搜索结果链接")
        path = unquote(parsed.path).rstrip("/") or "/"
        cleaned = f"https://www.youtube.com{path}"
        return cleaned

    raise SystemExit("无法识别输入。请提供 YouTube 频道主页 URL、@handle 或 channel id")


def build_candidate_urls(channel_url: str) -> list[str]:
    parsed = urlparse(channel_url)
    path = parsed.path.rstrip("/")
    candidates = [channel_url]
    if path and not path.endswith("/about"):
        candidates.append(f"https://www.youtube.com{path}/about")
    return candidates


def fetch_html(session, url: str, timeout: float) -> str:
    response = session.get(url, timeout=timeout, allow_redirects=True)
    response.raise_for_status()
    return response.text


def extract_meta_value(html_text: str, attr_name: str, attr_value: str) -> str:
    escaped = re.escape(attr_value)
    patterns = (
        rf'<meta[^>]+{attr_name}=["\']{escaped}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+{attr_name}=["\']{escaped}["\']',
    )
    return extract_first_match(html_text, patterns)


def extract_link_value(html_text: str, rel_value: str) -> str:
    escaped = re.escape(rel_value)
    patterns = (
        rf'<link[^>]+rel=["\']{escaped}["\'][^>]+href=["\']([^"\']+)["\']',
        rf'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']{escaped}["\']',
    )
    return extract_first_match(html_text, patterns)


def extract_first_match(text: str, patterns: Iterable[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return html.unescape(match.group(1)).strip()
    return ""


def extract_json_ld_objects(html_text: str) -> list[Dict[str, Any]]:
    objects: list[Dict[str, Any]] = []
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>\s*(.*?)\s*</script>',
        html_text,
        re.IGNORECASE | re.DOTALL,
    ):
        raw = html.unescape(match.group(1)).strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            objects.append(parsed)
        elif isinstance(parsed, list):
            objects.extend(item for item in parsed if isinstance(item, dict))
    return objects


def extract_json_ld_field(objects: list[Dict[str, Any]], field: str) -> str:
    for item in objects:
        value = item.get(field)
        resolved = normalize_json_ld_value(value)
        if resolved:
            return resolved
    return ""


def normalize_json_ld_value(value: Any) -> str:
    if isinstance(value, str):
        return html.unescape(value).strip()
    if isinstance(value, list):
        for item in value:
            resolved = normalize_json_ld_value(item)
            if resolved:
                return resolved
    if isinstance(value, dict):
        for key in ("url", "contentUrl"):
            inner = value.get(key)
            if isinstance(inner, str) and inner.strip():
                return html.unescape(inner).strip()
    return ""


def extract_channel_id(html_text: str) -> str:
    candidates = (
        extract_meta_value(html_text, "itemprop", "identifier"),
        extract_meta_value(html_text, "itemprop", "channelId"),
        extract_first_match(
            html_text,
            (
                r'"externalId":"(UC[\w-]{20,})"',
                r'"channelId":"(UC[\w-]{20,})"',
            ),
        ),
    )
    for candidate in candidates:
        if CHANNEL_ID_RE.fullmatch(candidate):
            return candidate
    return ""


def extract_handle(html_text: str, canonical_url: str) -> str:
    canonical_match = re.search(r"youtube\.com/(@[A-Za-z0-9._-]+)", canonical_url)
    if canonical_match:
        return canonical_match.group(1)

    handle = extract_first_match(
        html_text,
        (
            r'"canonicalBaseUrl":"(/@[A-Za-z0-9._-]+)"',
            r'"channelHandleText":\{"runs":\[\{"text":"(@[^"]+)"',
            r'"vanityChannelUrl":"https?://www\.youtube\.com/(@[A-Za-z0-9._-]+)"',
            r'"ownerUrls":\["https?://www\.youtube\.com/(@[A-Za-z0-9._-]+)"',
        ),
    )
    return handle.lstrip("/") if handle else ""


def extract_handle_from_target(target: str) -> str:
    value = target.strip()
    if HANDLE_RE.fullmatch(value):
        return value

    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        path = unquote(parsed.path).rstrip("/")
        last_segment = path.split("/")[-1] if path else ""
        if last_segment.startswith("@"):
            return last_segment
    return ""


def extract_profile(html_text: str, source_url: str, preferred_handle: str = "") -> Dict[str, str]:
    json_ld_objects = extract_json_ld_objects(html_text)

    canonical_url = (
        extract_link_value(html_text, "canonical")
        or extract_meta_value(html_text, "property", "og:url")
        or source_url
    )
    name = (
        extract_meta_value(html_text, "property", "og:title")
        or extract_meta_value(html_text, "itemprop", "name")
        or extract_json_ld_field(json_ld_objects, "name")
    )
    intro = (
        extract_meta_value(html_text, "property", "og:description")
        or extract_meta_value(html_text, "itemprop", "description")
        or extract_json_ld_field(json_ld_objects, "description")
    )
    avatar_url = (
        extract_meta_value(html_text, "property", "og:image")
        or extract_meta_value(html_text, "itemprop", "image")
        or extract_json_ld_field(json_ld_objects, "image")
    )
    channel_id = extract_channel_id(html_text)
    handle = extract_handle(html_text, canonical_url) or preferred_handle

    if not name or not canonical_url:
        raise YouTubeFetchError("未能从页面中解析出有效的 YouTube 博主信息")

    profile_url = source_url if preferred_handle else canonical_url
    creator_id = channel_id or handle or canonical_url
    return {
        "success": True,
        "platform": "YouTube",
        "mid": creator_id,
        "channel_id": channel_id,
        "creator_id": creator_id,
        "handle": handle,
        "name": name,
        "intro": intro,
        "description": intro,
        "avatar_url": avatar_url,
        "space_url": profile_url,
        "profile_url": profile_url,
    }


def fetch_profile(target: str, timeout: float) -> Dict[str, str]:
    """通过 YouTube 公开频道页获取博主基础信息。"""
    channel_url = normalize_target(target)
    preferred_handle = extract_handle_from_target(target)
    session = create_session()
    last_error: Optional[Exception] = None

    for candidate_url in build_candidate_urls(channel_url):
        try:
            html_text = fetch_html(session, candidate_url, timeout)
            return extract_profile(html_text, channel_url, preferred_handle)
        except Exception as exc:
            last_error = exc

    if last_error is None:
        raise YouTubeFetchError("未能从页面中解析出有效的 YouTube 博主信息")
    raise YouTubeFetchError(str(last_error)) from last_error


def write_output(profile: Dict[str, str], output: Optional[str], indent: int) -> None:
    text = json.dumps(profile, ensure_ascii=False, indent=indent)
    print(text)
    if output:
        Path(output).expanduser().write_text(text + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()

    try:
        profile = fetch_profile(args.target, args.timeout)
        write_output(profile, args.output, args.indent)
        return 0
    except Exception as exc:
        error_payload = {
            "success": False,
            "source": args.target,
            "error": str(exc),
        }
        print(json.dumps(error_payload, ensure_ascii=False, indent=args.indent), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
