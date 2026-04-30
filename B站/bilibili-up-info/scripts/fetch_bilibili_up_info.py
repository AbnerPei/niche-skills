#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch basic profile information from a Bilibili UP homepage.

The script accepts either a numeric mid or a space URL like:
https://space.bilibili.com/3493270319520448
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlencode, urlparse


NAV_API = "https://api.bilibili.com/x/web-interface/nav"
FINGER_SPI_API = "https://api.bilibili.com/x/frontend/finger/spi"
SPACE_INFO_API = "https://api.bilibili.com/x/space/wbi/acc/info"
LEGACY_SPACE_INFO_API = "https://api.bilibili.com/x/space/acc/info"
CARD_API = "https://api.bilibili.com/x/web-interface/card"
SPACE_URL = "https://space.bilibili.com/{mid}"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Bilibili WBI signature mixin table. This is required by the current space API.
MIXIN_KEY_ENC_TAB = [
    46,
    47,
    18,
    2,
    53,
    8,
    23,
    32,
    15,
    50,
    10,
    31,
    58,
    3,
    45,
    35,
    27,
    43,
    5,
    49,
    33,
    9,
    42,
    19,
    29,
    28,
    14,
    39,
    12,
    38,
    41,
    13,
    37,
    48,
    7,
    16,
    24,
    55,
    40,
    61,
    26,
    17,
    0,
    1,
    60,
    51,
    30,
    4,
    22,
    25,
    54,
    21,
    56,
    59,
    6,
    63,
    57,
    62,
    11,
    36,
    20,
    34,
    44,
    52,
]


class BilibiliFetchError(RuntimeError):
    """Raised when Bilibili returns an unusable response."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="抓取 B 站 UP 主页基础信息：UP主名字、介绍、头像 URL。",
    )
    parser.add_argument(
        "target",
        help="UP 主 mid，或 B 站空间主页 URL，例如 https://space.bilibili.com/123456",
    )
    parser.add_argument(
        "--cookie",
        default=os.environ.get("BILIBILI_COOKIE", ""),
        help="可选。B 站 Cookie 字符串；也可通过 BILIBILI_COOKIE 环境变量提供。",
    )
    parser.add_argument(
        "--cookie-file",
        help="可选。读取 Cookie 的文本文件路径，优先级高于 --cookie。",
    )
    parser.add_argument(
        "--download-avatar",
        action="store_true",
        help="同时下载头像文件，并在输出 JSON 中写入 avatar_path。",
    )
    parser.add_argument(
        "--avatar-dir",
        default="bilibili_avatars",
        help="头像下载目录，仅在 --download-avatar 时生效。默认：bilibili_avatars",
    )
    parser.add_argument(
        "--output",
        help="可选。把结果 JSON 写入指定文件；不传则只输出到 stdout。",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=12.0,
        help="请求超时时间，单位秒。默认：12",
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


def extract_mid(target: str) -> str:
    value = target.strip()
    if re.fullmatch(r"\d+", value):
        return value

    parsed = urlparse(value)
    candidates = [parsed.path, parsed.query, value]
    for text in candidates:
        match = re.search(r"(?:space\.bilibili\.com/|^|[?&]mid=|[?&]vmid=)(\d{2,})", text)
        if match:
            return match.group(1)

    raise SystemExit(f"无法从输入中解析 UP 主 mid：{target}")


def read_cookie(cookie: str, cookie_file: Optional[str]) -> str:
    if cookie_file:
        return Path(cookie_file).expanduser().read_text(encoding="utf-8").strip()
    return cookie.strip()


def create_session(cookie: str):
    requests = require_requests()
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://space.bilibili.com/",
            "Origin": "https://space.bilibili.com",
        }
    )
    if cookie:
        session.headers["Cookie"] = cookie
    return session


def prime_anonymous_buvid(session, timeout: float, cookie: str) -> None:
    if cookie and ("buvid3=" in cookie or "buvid4=" in cookie):
        return
    try:
        payload = request_json(session, FINGER_SPI_API, None, timeout)
    except Exception:
        return

    data = payload.get("data") or {}
    buvid3 = data.get("b_3")
    buvid4 = data.get("b_4")
    if buvid3:
        session.cookies.set("buvid3", buvid3, domain=".bilibili.com")
    if buvid4:
        session.cookies.set("buvid4", buvid4, domain=".bilibili.com")
    session.cookies.set("b_nut", str(int(time.time())), domain=".bilibili.com")


def request_json(
    session,
    url: str,
    params: Optional[Dict[str, Any]],
    timeout: float,
    allowed_codes: Iterable[Optional[int]] = (0, None),
) -> Dict[str, Any]:
    response = session.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise BilibiliFetchError(f"B 站返回的不是 JSON：{response.text[:200]}") from exc

    code = payload.get("code")
    if code not in allowed_codes:
        message = payload.get("message") or payload.get("msg") or "unknown error"
        raise BilibiliFetchError(f"B 站接口返回失败 code={code}, message={message}")
    return payload


def basename_without_ext(url: str) -> str:
    path = urlparse(url).path
    return Path(path).stem


def get_mixin_key(img_key: str, sub_key: str) -> str:
    raw_key = img_key + sub_key
    return "".join(raw_key[index] for index in MIXIN_KEY_ENC_TAB)[:32]


def get_wbi_mixin_key(session, timeout: float) -> str:
    payload = request_json(session, NAV_API, None, timeout, allowed_codes=(0, -101, None))
    wbi_img = payload.get("data", {}).get("wbi_img", {})
    img_url = wbi_img.get("img_url", "")
    sub_url = wbi_img.get("sub_url", "")
    if not img_url or not sub_url:
        raise BilibiliFetchError("未能从 nav 接口取得 WBI 签名 key")
    return get_mixin_key(basename_without_ext(img_url), basename_without_ext(sub_url))


def clean_wbi_value(value: Any) -> str:
    return re.sub(r"[!'()*]", "", str(value))


def sign_wbi_params(params: Dict[str, Any], mixin_key: str) -> Dict[str, Any]:
    signed = {key: clean_wbi_value(value) for key, value in params.items()}
    signed["wts"] = int(time.time())
    query = urlencode(sorted(signed.items()))
    signed["w_rid"] = hashlib.md5((query + mixin_key).encode("utf-8")).hexdigest()
    return signed


def normalize_url(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    return url


def select_profile_fields(mid: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "success": True,
        "mid": mid,
        "name": data.get("name", ""),
        "intro": data.get("sign", ""),
        "avatar_url": normalize_url(data.get("face", "")),
        "space_url": SPACE_URL.format(mid=mid),
    }


def fetch_profile(session, mid: str, timeout: float) -> Dict[str, Any]:
    try:
        mixin_key = get_wbi_mixin_key(session, timeout)
        params = sign_wbi_params(
            {
                "mid": mid,
                "token": "",
                "platform": "web",
                "web_location": "1550101",
                "dm_img_list": "[]",
                "dm_img_str": "V2ViR0wgMS4wIChPcGVuR0wgRVMgMi4wIENocm9taXVtKQ",
                "dm_cover_img_str": (
                    "QU5HTEUgKEludGVsLCBJbnRlbChSKSBIRCBHcmFwaGljcyBEaXJlY3QzRDEx"
                    "IHZzXzVfMCBwc181XzApR29vZ2xlIEluYy4gKEludGVsKQ"
                ),
                "dm_img_inter": '{"ds":[],"wh":[0,0,0],"of":[0,0,0]}',
            },
            mixin_key,
        )
        payload = request_json(session, SPACE_INFO_API, params, timeout)
    except Exception as exc:
        # Keep a legacy fallback because the unsigned endpoint still works in
        # some environments and is useful when WBI bootstrap is blocked.
        try:
            payload = request_json(session, LEGACY_SPACE_INFO_API, {"mid": mid}, timeout)
        except Exception as fallback_exc:
            try:
                card_payload = request_json(session, CARD_API, {"mid": mid}, timeout)
            except Exception as card_exc:
                raise BilibiliFetchError(
                    f"WBI 接口失败：{exc}；旧接口也失败：{fallback_exc}；card 接口也失败：{card_exc}"
                ) from card_exc
            card = card_payload.get("data", {}).get("card") or {}
            if not card:
                raise BilibiliFetchError("card 接口返回成功，但 card 为空") from fallback_exc
            return select_profile_fields(mid, card)

    data = payload.get("data") or {}
    if not data:
        raise BilibiliFetchError("接口返回成功，但 data 为空")
    return select_profile_fields(mid, data)


def guess_avatar_suffix(url: str, content_type: str) -> str:
    path_suffix = Path(urlparse(url).path).suffix
    if path_suffix:
        return path_suffix.split("@", 1)[0]
    if "png" in content_type:
        return ".png"
    if "webp" in content_type:
        return ".webp"
    return ".jpg"


def safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\s]+", "_", value).strip("_")
    return cleaned or "up"


def download_avatar(session, profile: Dict[str, Any], avatar_dir: str, timeout: float) -> str:
    avatar_url = profile.get("avatar_url", "")
    if not avatar_url:
        raise BilibiliFetchError("头像 URL 为空，无法下载")

    response = session.get(avatar_url, timeout=timeout)
    response.raise_for_status()
    suffix = guess_avatar_suffix(avatar_url, response.headers.get("Content-Type", ""))
    filename = f"{profile['mid']}_{safe_filename_part(profile['name'])}{suffix}"
    output_dir = Path(avatar_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    output_path.write_bytes(response.content)
    return str(output_path.resolve())


def write_output(profile: Dict[str, Any], output: Optional[str], indent: int) -> None:
    text = json.dumps(profile, ensure_ascii=False, indent=indent)
    print(text)
    if output:
        Path(output).expanduser().write_text(text + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    mid = extract_mid(args.target)
    cookie = read_cookie(args.cookie, args.cookie_file)
    session = create_session(cookie)
    prime_anonymous_buvid(session, args.timeout, cookie)

    try:
        profile = fetch_profile(session, mid, args.timeout)
        if args.download_avatar:
            profile["avatar_path"] = download_avatar(session, profile, args.avatar_dir, args.timeout)
        write_output(profile, args.output, args.indent)
        return 0
    except Exception as exc:
        error_payload = {"success": False, "mid": mid, "error": str(exc)}
        print(json.dumps(error_payload, ensure_ascii=False, indent=args.indent), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
