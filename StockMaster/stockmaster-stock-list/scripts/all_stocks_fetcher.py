#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全市场股票信息获取器

优先使用东方财富分交易所接口抓取；当分页接口异常、数量明显偏少、
或交易所返回不完整时，自动回退到 AkShare 的完整 A 股列表重建。

为了尽量让结果和同花顺网页保持一致，会额外抓取同花顺网页样本页做校验：
1. 解析总页数，推导合理的总量范围
2. 抽样校验网页中的代码/名称是否都能在结果集中找到
3. 当普通请求被同花顺风控拦截时，尝试使用 Scrapling 浏览器态抓取兜底
"""

from __future__ import annotations

import os
import random
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HELP_REQUESTED = any(arg in ("-h", "--help") for arg in sys.argv[1:])

try:
    import requests
    import pandas as pd
except ModuleNotFoundError:
    if not HELP_REQUESTED:
        raise
    requests = None  # type: ignore[assignment]
    pd = None  # type: ignore[assignment]

try:
    import akshare as ak
except ModuleNotFoundError:
    if not HELP_REQUESTED:
        ak = None  # type: ignore[assignment]
    else:
        ak = None  # type: ignore[assignment]

try:
    from bs4 import BeautifulSoup
except ModuleNotFoundError:
    if not HELP_REQUESTED:
        BeautifulSoup = None  # type: ignore[assignment]
    else:
        BeautifulSoup = None  # type: ignore[assignment]

try:
    from scrapling.fetchers import StealthyFetcher
except ModuleNotFoundError:
    StealthyFetcher = None  # type: ignore[assignment]


DEFAULT_OUTPUT_DIR = os.environ.get(
    "STOCKMASTER_STOCK_LIST_DATA_DIR",
    os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "stock_list")
    ),
)


class AllStocksFetcher:
    """全市场股票信息获取器"""

    THS_PAGE_URL = (
        "https://q.10jqka.com.cn/index/index/board/all/field/zdf/order/desc/page/{page}/ajax/1/"
    )
    THS_PAGE_SIZE = 20
    IPO_LOOKBACK_DAYS = 90
    RECENT_LISTED_IPOS_FILE = "recent_listed_ipos.csv"
    PENDING_IPOS_FILE = "pending_ipos.csv"

    def __init__(self, output_dir: str | None = None):
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.ensure_output_dir()

        self.exchanges = {
            "SSE": {
                "name": "上海证券交易所",
                "file": "sse_stocks.csv",
                "min_expected": 2000,
            },
            "SZSE": {
                "name": "深圳证券交易所",
                "file": "szse_stocks.csv",
                "min_expected": 2500,
            },
            "BSE": {
                "name": "北京证券交易所",
                "file": "bse_stocks.csv",
                "min_expected": 250,
            },
        }

        self.api_config = {
            "eastmoney_base": "http://push2.eastmoney.com/api/qt/clist/get",
            "timeout": 15,
            "max_retries": 3,
            "retry_delay": 2,
        }

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
                "image/webp,image/apng,*/*;q=0.8"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.google.com/",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Upgrade-Insecure-Requests": "1",
            "sec-ch-ua": '"Chromium";v="145", "Google Chrome";v="145", "Not.A/Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
        }
        self.ths_cookie_header = os.environ.get("STOCKMASTER_THS_COOKIE", "").strip()
        self.ths_v_cookie = os.environ.get("STOCKMASTER_THS_V_COOKIE", "").strip()
        self.ths_vvvv_cookie = os.environ.get("STOCKMASTER_THS_VVVV_COOKIE", "").strip()

        self.backup_headers = [
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
                ),
                "Accept": self.headers["Accept"],
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://www.baidu.com/",
                "Connection": "keep-alive",
            },
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh-Hans;q=0.9",
                "Referer": "https://www.google.com/",
                "Connection": "keep-alive",
            },
        ]

    def ensure_output_dir(self) -> None:
        """确保输出目录存在"""
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def normalize_stock_name(self, stock_name: str) -> str:
        """去掉名称中的多余空白，便于做来源间校验"""
        return re.sub(r"\s+", "", (stock_name or "")).strip()

    def stock_name_variants(self, stock_name: str) -> set[str]:
        """兼容不同源对 IPO 前缀和特殊表决权后缀的简称展示差异。"""
        normalized = self.normalize_stock_name(stock_name)
        variants = {normalized}

        stripped_prefix = re.sub(r"^[CN]", "", normalized)
        if stripped_prefix:
            variants.add(stripped_prefix)

        stripped_suffix = re.sub(r"-(U|W|V)$", "", normalized)
        if stripped_suffix:
            variants.add(stripped_suffix)

        stripped_both = re.sub(r"-(U|W|V)$", "", stripped_prefix)
        if stripped_both:
            variants.add(stripped_both)

        return {item for item in variants if item}

    def stock_names_match(self, actual_name: str, expected_name: str) -> bool:
        """允许同义简称在不同数据源之间通过校验。"""
        return not self.stock_name_variants(actual_name).isdisjoint(
            self.stock_name_variants(expected_name)
        )

    def is_st_stock_name(self, stock_name: str) -> bool:
        """标记 ST，但不再过滤掉它们"""
        name = (stock_name or "").strip().upper()
        return name.startswith(("ST", "*ST", "S*ST", "PT"))

    def validate_stock_code(self, stock_code: str, exchange: str) -> bool:
        """验证股票代码格式是否符合交易所规范"""
        if not stock_code or len(stock_code) != 6 or not stock_code.isdigit():
            return False

        if exchange == "SSE":
            return stock_code.startswith(("60", "68"))
        if exchange == "SZSE":
            return stock_code.startswith(("00", "30"))
        if exchange == "BSE":
            return stock_code.startswith("92")
        return False

    def infer_exchange_from_code(self, stock_code: str) -> Optional[str]:
        """根据股票代码推断所属交易所，用于新股补充和兜底校验。"""
        if stock_code.startswith(("60", "68")):
            return "SSE"
        if stock_code.startswith(("00", "30")):
            return "SZSE"
        if stock_code.startswith("92"):
            return "BSE"
        return None

    def parse_maybe_date(self, value: Any) -> Optional[datetime]:
        """兼容 pandas/date/datetime/字符串等日期格式。"""
        if value is None:
            return None
        if pd is not None and pd.isna(value):
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        if hasattr(value, "to_pydatetime"):
            try:
                converted = value.to_pydatetime()
                if isinstance(converted, datetime):
                    return converted
            except Exception:
                pass

        text = str(value).strip()
        if not text or text.lower() == "nat":
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None

    def should_supplement_stock_list_with_ipo(
        self,
        ipo_date: Optional[datetime],
        listing_date: Optional[datetime],
    ) -> bool:
        """仅用于主股票列表补齐。

        主股票列表的目标仍然是“当前可交易股票”为主；这里保留一个近期窗口，
        只是为了兼容同花顺网页会提前展示待上市/刚上市新股的情况。
        这不是“新股上市”的业务定义，真实上市视图会单独按上市日期落盘。
        """
        now = datetime.now()
        recent_threshold = now - timedelta(days=self.IPO_LOOKBACK_DAYS)
        if listing_date is not None:
            return listing_date >= recent_threshold
        if ipo_date is not None:
            return ipo_date >= recent_threshold
        return False

    def build_ipo_note(
        self,
        source: str,
        ipo_date: Optional[datetime],
        listing_date: Optional[datetime],
    ) -> str:
        """将新股补充来源压缩成一条可读日志。"""
        ipo_text = ipo_date.strftime("%Y-%m-%d") if ipo_date else "未知申购日"
        listing_text = listing_date.strftime("%Y-%m-%d") if listing_date else "待上市"
        return f"{source}, 申购日 {ipo_text}, 上市日 {listing_text}"

    def build_ipo_output_record(self, stock_code: str, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """统一输出 IPO 视图行，保持股票代码字符串化并显式区分状态。"""
        ipo_date = candidate.get("ipo_date")
        listing_date = candidate.get("listing_date")
        return {
            "股票代码": str(stock_code).zfill(6),
            "股票名称": str(candidate.get("name") or "").strip(),
            "交易所": self.exchanges[str(candidate["exchange"])]["name"],
            "交易所代码": str(candidate["exchange"]),
            "申购日期": ipo_date.strftime("%Y-%m-%d") if isinstance(ipo_date, datetime) else "",
            "上市日期": listing_date.strftime("%Y-%m-%d") if isinstance(listing_date, datetime) else "",
            "状态": "已上市" if listing_date is not None else "待上市",
            "来源": " | ".join(candidate.get("notes") or []),
        }

    def build_requests_session(
        self,
        headers: dict | None = None,
    ) -> requests.Session:
        """为同花顺请求构建可复用 session，并注入外部提供的登录态 cookie。"""
        if requests is None:
            raise RuntimeError("缺少 requests 依赖")

        session = requests.Session()
        session.headers.update(headers or self.headers)

        if self.ths_cookie_header:
            session.headers["Cookie"] = self.ths_cookie_header
        if self.ths_v_cookie:
            session.cookies.set("v", self.ths_v_cookie, domain=".10jqka.com.cn", path="/")
        if self.ths_vvvv_cookie:
            session.cookies.set("vvvv", self.ths_vvvv_cookie, domain="q.10jqka.com.cn", path="/")
        return session

    def make_request_with_retry(
        self,
        url: str,
        headers: dict | None = None,
        max_retries: int = 3,
        session: requests.Session | None = None,
    ) -> requests.Response:
        """带重试机制的请求方法"""
        if requests is None:
            raise RuntimeError("缺少 requests 依赖")

        current_headers = dict(headers or self.headers)
        session = session or requests.Session()
        last_exception: Exception | None = None

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    delay = random.uniform(1, 3) + attempt * 0.5
                    time.sleep(delay)
                    current_headers = random.choice(self.backup_headers)
                    print(f"第{attempt + 1}次尝试，切换备用请求头")

                response = session.get(
                    url,
                    headers=current_headers,
                    timeout=self.api_config["timeout"],
                )
                if response.status_code == 200:
                    return response
                if response.status_code in {401, 403, 429, 502, 503}:
                    last_exception = requests.exceptions.RequestException(
                        f"HTTP {response.status_code}"
                    )
                    print(f"第{attempt + 1}次请求返回 {response.status_code}: {url}")
                    continue
                response.raise_for_status()
            except requests.exceptions.RequestException as exc:
                last_exception = exc
                print(f"第{attempt + 1}次请求失败: {exc}")

        if last_exception is not None:
            raise last_exception
        raise requests.exceptions.RequestException(f"请求失败，已重试{max_retries}次")

    def build_stock_record(self, exchange: str, stock_code: str, stock_name: str) -> Dict[str, Any]:
        """统一构建 CSV 行数据，保持股票代码为字符串，并补齐 ST 标记"""
        return {
            "股票代码": stock_code,
            "股票名称": stock_name,
            "交易所": self.exchanges[exchange]["name"],
            "交易所代码": exchange,
            "是否ST": 1 if self.is_st_stock_name(stock_name) else 0,
        }

    def get_all_stocks_eastmoney(self, exchange: str) -> List[Dict[str, Any]]:
        """使用东方财富接口获取指定交易所股票信息"""
        if requests is None:
            raise RuntimeError("缺少 requests 依赖")

        stocks: List[Dict[str, Any]] = []
        seen_codes: set[str] = set()
        page = 1
        page_size = 100
        total_pages = 0

        if exchange == "SSE":
            fs_param = "m:1+t:2,m:1+t:23"
        elif exchange == "SZSE":
            fs_param = "m:0+t:6,m:0+t:13,m:0+t:80"
        elif exchange == "BSE":
            fs_param = "m:0+t:81+s:2048"
        else:
            return stocks

        print(f"开始通过东方财富获取 {self.exchanges[exchange]['name']} 股票列表...")

        while True:
            try:
                params = {
                    "pn": page,
                    "pz": page_size,
                    "po": "1",
                    "np": "1",
                    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                    "fltt": "2",
                    "invt": "2",
                    "fid": "f3",
                    "fs": fs_param,
                    "fields": "f12,f14",
                }
                import urllib.parse

                full_url = f"{self.api_config['eastmoney_base']}?{urllib.parse.urlencode(params)}"
                print(f"东方财富：正在获取 {exchange} 第 {page} 页...")
                response = self.make_request_with_retry(full_url)
                data = response.json()

                payload = data.get("data") or {}
                stock_list = payload.get("diff") or []
                if total_pages == 0:
                    total_count = int(payload.get("total") or 0)
                    if total_count > 0:
                        total_pages = (total_count + page_size - 1) // page_size
                        print(f"东方财富：{exchange} 预计总数 {total_count}，总页数 {total_pages}")

                if not stock_list:
                    print(f"东方财富：{exchange} 第 {page} 页无数据，停止")
                    break

                current_page_count = 0
                for stock in stock_list:
                    stock_code = str(stock.get("f12") or "").zfill(6)
                    stock_name = str(stock.get("f14") or "").strip()
                    if not self.validate_stock_code(stock_code, exchange):
                        continue
                    if not stock_name or stock_code in seen_codes:
                        continue
                    seen_codes.add(stock_code)
                    stocks.append(self.build_stock_record(exchange, stock_code, stock_name))
                    current_page_count += 1

                print(
                    f"东方财富：{exchange} 第 {page} 页新增 {current_page_count} 只，累计 {len(stocks)} 只"
                )

                if total_pages > 0 and page >= total_pages:
                    break
                if len(stock_list) < page_size:
                    break
                if page > 50:
                    print("东方财富：命中 50 页安全上限，停止")
                    break

                page += 1
                time.sleep(0.8)
            except Exception as exc:
                print(f"东方财富：获取 {exchange} 第 {page} 页失败: {exc}")
                break

        print(f"东方财富：{exchange} 最终获取 {len(stocks)} 只股票")
        return stocks

    def get_exchange_stocks_akshare(self, exchange: str) -> List[Dict[str, Any]]:
        """使用 AkShare 获取完整交易所列表，作为稳定兜底"""
        if ak is None or pd is None:
            raise RuntimeError("缺少 akshare 或 pandas 依赖，无法执行完整股票列表兜底")

        print(f"AkShare：开始重建 {self.exchanges[exchange]['name']} 股票列表...")

        if exchange == "SSE":
            sh_main = ak.stock_info_sh_name_code(symbol="主板A股")[["证券代码", "证券简称"]]
            sh_kcb = ak.stock_info_sh_name_code(symbol="科创板")[["证券代码", "证券简称"]]
            df = pd.concat([sh_main, sh_kcb], ignore_index=True)
            df.columns = ["code", "name"]
        elif exchange == "SZSE":
            df = ak.stock_info_sz_name_code(symbol="A股列表")[["A股代码", "A股简称"]].copy()
            df["A股代码"] = df["A股代码"].astype(str).str.zfill(6)
            df.columns = ["code", "name"]
        elif exchange == "BSE":
            df = ak.stock_info_bj_name_code()[["证券代码", "证券简称"]].copy()
            df["证券代码"] = df["证券代码"].astype(str).str.zfill(6)
            df.columns = ["code", "name"]
        else:
            return []

        stocks: List[Dict[str, Any]] = []
        seen_codes: set[str] = set()
        for row in df.to_dict(orient="records"):
            stock_code = str(row["code"]).zfill(6)
            stock_name = str(row["name"]).strip()
            if not self.validate_stock_code(stock_code, exchange):
                continue
            if not stock_name or stock_code in seen_codes:
                continue
            seen_codes.add(stock_code)
            stocks.append(self.build_stock_record(exchange, stock_code, stock_name))

        print(f"AkShare：{exchange} 重建完成，共 {len(stocks)} 只股票")
        return stocks

    def get_all_exchange_stocks_akshare(self) -> Dict[str, List[Dict[str, Any]]]:
        """整市场使用 AkShare 重建，便于在混合抓取失败后整体回退"""
        rebuilt: Dict[str, List[Dict[str, Any]]] = {}
        for exchange in self.exchanges.keys():
            rebuilt[exchange] = self.get_exchange_stocks_akshare(exchange)
        return rebuilt

    def ths_page_has_table(self, html: str) -> bool:
        """判断同花顺页面是否真的返回了股票表格"""
        if not html:
            return False
        if "m-pager-table" not in html:
            return False
        if "同花顺-用户登录" in html:
            return False
        if "Nginx forbidden" in html:
            return False
        if "window.location.href" in html and "m-pager-table" not in html:
            return False
        return True

    def parse_ths_rows(self, html: str) -> List[Dict[str, str]]:
        """解析同花顺网页中的代码和名称，用作校验基准"""
        if BeautifulSoup is None:
            raise RuntimeError("缺少 beautifulsoup4 依赖，无法解析同花顺网页")

        soup = BeautifulSoup(html, "html.parser")
        rows: List[Dict[str, str]] = []
        for tr in soup.select("table.m-table.m-pager-table tr")[1:]:
            cells = tr.select("td")
            if len(cells) < 3:
                continue
            stock_code = cells[1].get_text(strip=True)
            stock_name = cells[2].get_text(" ", strip=True)
            if re.fullmatch(r"\d{6}", stock_code):
                rows.append({"code": stock_code, "name": stock_name})
        return rows

    def parse_ths_page_info(self, html: str) -> Tuple[Optional[int], Optional[int]]:
        """解析同花顺分页信息"""
        match = re.search(r'<span class="page_info">(\d+)/(\d+)</span>', html)
        if not match:
            return None, None
        return int(match.group(1)), int(match.group(2))

    def fetch_ths_page_via_requests(self, page: int) -> Optional[str]:
        """普通请求抓同花顺页面。深页可能触发风控，因此只作为第一层尝试。"""
        if requests is None:
            return None

        url = self.THS_PAGE_URL.format(page=page)
        session = self.build_requests_session()

        try:
            if page > 1:
                warm_up = session.get(self.THS_PAGE_URL.format(page=1), timeout=20)
                print(
                    f"同花顺校验：requests 预热 page=1 状态 {warm_up.status_code}，目标页 page={page}"
                )
                time.sleep(0.4)

            response = session.get(url, timeout=20)
            html = response.text
            print(f"同花顺校验：requests page={page} 状态 {response.status_code}")
            if self.ths_page_has_table(html):
                return html
            return None
        except Exception as exc:
            print(f"同花顺校验：requests page={page} 失败: {exc}")
            return None

    def collect_ipo_candidates(self) -> Dict[str, Dict[str, Any]]:
        """收集 IPO 候选并保留精确状态。

        这里不再用“近 90 天”定义新股上市，而是直接保留源里的申购/上市日期：
        - 有 `上市日期` => 已上市新股
        - 无 `上市日期` => 待上市新股
        """
        if ak is None or pd is None:
            print("IPO 候选：缺少 akshare 或 pandas，跳过新股状态收集")
            return {}

        candidates: Dict[str, Dict[str, Any]] = {}

        def ingest_candidate(
            stock_code: str,
            stock_name: str,
            ipo_date: Optional[datetime],
            listing_date: Optional[datetime],
            source: str,
        ) -> None:
            exchange = self.infer_exchange_from_code(stock_code)
            if exchange is None:
                return
            if not self.validate_stock_code(stock_code, exchange):
                return
            if not stock_name.strip():
                return

            note = self.build_ipo_note(source, ipo_date, listing_date)
            existing = candidates.get(stock_code)
            if existing is None:
                candidates[stock_code] = {
                    "exchange": exchange,
                    "name": stock_name.strip(),
                    "ipo_date": ipo_date,
                    "listing_date": listing_date,
                    "notes": [note],
                }
                return

            if stock_name.strip():
                existing["name"] = stock_name.strip()
            if listing_date and (
                existing["listing_date"] is None or listing_date > existing["listing_date"]
            ):
                existing["listing_date"] = listing_date
            if ipo_date and (existing["ipo_date"] is None or ipo_date > existing["ipo_date"]):
                existing["ipo_date"] = ipo_date
            if note not in existing["notes"]:
                existing["notes"].append(note)

        try:
            em_df = ak.stock_xgsglb_em()
            for row in em_df.to_dict(orient="records"):
                stock_code = str(row.get("股票代码") or "").zfill(6)
                stock_name = str(row.get("股票简称") or "").strip()
                ipo_date = self.parse_maybe_date(row.get("申购日期"))
                listing_date = self.parse_maybe_date(row.get("上市日期"))
                ingest_candidate(stock_code, stock_name, ipo_date, listing_date, "东方财富新股")
            print(f"IPO 候选：东方财富新股源扫描完成，候选 {len(candidates)} 只")
        except Exception as exc:
            print(f"IPO 候选：东方财富新股源失败: {exc}")

        try:
            cninfo_df = ak.stock_new_ipo_cninfo()
            for row in cninfo_df.to_dict(orient="records"):
                stock_code = str(row.get("证劵代码") or "").zfill(6)
                stock_name = str(row.get("证券简称") or "").strip()
                ipo_date = self.parse_maybe_date(row.get("申购日期"))
                listing_date = self.parse_maybe_date(row.get("上市日期"))
                ingest_candidate(stock_code, stock_name, ipo_date, listing_date, "巨潮新股")
            print(f"IPO 候选：巨潮新股源扫描完成，候选 {len(candidates)} 只")
        except Exception as exc:
            print(f"IPO 候选：巨潮新股源失败: {exc}")

        return candidates

    def save_ipo_views(self, candidates: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
        """把 IPO 候选显式拆成“已上市新股”和“待上市新股”两份 CSV。"""
        if pd is None:
            raise RuntimeError("缺少 pandas 依赖")

        listed_rows: List[Dict[str, Any]] = []
        pending_rows: List[Dict[str, Any]] = []
        for stock_code in sorted(candidates.keys()):
            row = self.build_ipo_output_record(stock_code, candidates[stock_code])
            if row["上市日期"]:
                listed_rows.append(row)
            else:
                pending_rows.append(row)

        columns = ["股票代码", "股票名称", "交易所", "交易所代码", "申购日期", "上市日期", "状态", "来源"]

        listed_df = pd.DataFrame(listed_rows, columns=columns)
        pending_df = pd.DataFrame(pending_rows, columns=columns)
        if not listed_df.empty:
            listed_df = listed_df.sort_values(
                by=["上市日期", "股票代码"],
                ascending=[False, True],
                na_position="last",
            )
        if not pending_df.empty:
            pending_df = pending_df.sort_values(
                by=["申购日期", "股票代码"],
                ascending=[False, True],
                na_position="last",
            )

        listed_path = os.path.join(self.output_dir, self.RECENT_LISTED_IPOS_FILE)
        pending_path = os.path.join(self.output_dir, self.PENDING_IPOS_FILE)
        listed_df.to_csv(listed_path, index=False, encoding="utf-8-sig")
        pending_df.to_csv(pending_path, index=False, encoding="utf-8-sig")

        print(f"IPO 视图：已上市新股 {len(listed_df)} 只 -> {listed_path}")
        print(f"IPO 视图：待上市新股 {len(pending_df)} 只 -> {pending_path}")
        return {
            "listed": int(len(listed_df)),
            "pending": int(len(pending_df)),
        }

    def merge_recent_ipo_candidates(
        self,
        stocks_by_exchange: Dict[str, List[Dict[str, Any]]],
        candidates: Dict[str, Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, str]]]:
        """把近期新股补到全市场列表里，并把补入明细打印到刷新日志。"""
        if not candidates:
            print("新股补充：未找到需要补入的候选股票")
            return {}

        existing_codes = {
            stock["股票代码"]
            for stocks in stocks_by_exchange.values()
            for stock in stocks
        }
        additions_by_exchange: Dict[str, List[Dict[str, str]]] = {key: [] for key in self.exchanges.keys()}

        for stock_code in sorted(candidates.keys()):
            if stock_code in existing_codes:
                continue

            candidate = candidates[stock_code]
            ipo_date = candidate.get("ipo_date")
            listing_date = candidate.get("listing_date")
            if not self.should_supplement_stock_list_with_ipo(ipo_date, listing_date):
                continue
            exchange = str(candidate["exchange"])
            stock_name = str(candidate["name"])
            notes = list(candidate["notes"])
            stocks_by_exchange[exchange].append(self.build_stock_record(exchange, stock_code, stock_name))
            additions_by_exchange[exchange].append(
                {
                    "code": stock_code,
                    "name": stock_name,
                    "note": " | ".join(notes),
                }
            )
            existing_codes.add(stock_code)

        added_total = sum(len(items) for items in additions_by_exchange.values())
        if added_total == 0:
            print("新股补充：候选股票均已在主列表中，无需额外补入")
            return additions_by_exchange

        print(f"新股补充：共补入 {added_total} 只同花顺已展示的待上市/新股")
        for exchange, items in additions_by_exchange.items():
            if not items:
                continue
            print(f"新股补充：{exchange} 新增 {len(items)} 只")
            for item in items:
                print(f"  + {item['code']} {item['name']} ({item['note']})")

        return additions_by_exchange

    def fetch_ths_page_via_scrapling(self, page: int) -> Optional[str]:
        """当普通请求触发风控时，使用 Scrapling 浏览器态抓取兜底。"""
        if StealthyFetcher is None:
            print("同花顺校验：当前 Python 环境未安装 Scrapling，跳过浏览器态兜底")
            return None

        try:
            url = self.THS_PAGE_URL.format(page=page)
            fetcher = StealthyFetcher()
            response = fetcher.fetch(url, headless=True, timeout=45000)
            body = response.body
            html = (
                body.decode("utf-8", "ignore")
                if isinstance(body, (bytes, bytearray))
                else str(body or "")
            )
            print(
                f"同花顺校验：Scrapling page={page} 状态 {getattr(response, 'status', 'unknown')}"
            )
            if self.ths_page_has_table(html):
                return html
            return None
        except Exception as exc:
            print(f"同花顺校验：Scrapling page={page} 失败: {exc}")
            return None

    def fetch_ths_page(self, page: int) -> Optional[str]:
        """组合使用 requests 与 Scrapling 获取同花顺样本页"""
        html = self.fetch_ths_page_via_requests(page)
        if html:
            return html
        print(f"同花顺校验：page={page} 触发风控，切换 Scrapling 兜底")
        return self.fetch_ths_page_via_scrapling(page)

    def fetch_ths_reference_snapshot(self, sample_pages: int = 3) -> Optional[Dict[str, Any]]:
        """抓取同花顺网页样本页，用作总量和代码名称校验"""
        print("同花顺校验：开始抓取网页样本...")
        first_html = self.fetch_ths_page(1)
        if not first_html:
            print("同花顺校验：未能获取 page=1，跳过网页校验")
            return None

        first_rows = self.parse_ths_rows(first_html)
        _, total_pages = self.parse_ths_page_info(first_html)
        snapshot: Dict[str, Any] = {
            "total_pages": total_pages,
            "page_size": len(first_rows) or self.THS_PAGE_SIZE,
            "samples": {1: first_rows},
        }

        print(
            "同花顺校验："
            f"page=1 抓到 {len(first_rows)} 条样本，"
            f"总页数 {total_pages or '未知'}"
        )

        for page in range(2, sample_pages + 1):
            html = self.fetch_ths_page(page)
            if not html:
                print(f"同花顺校验：page={page} 未拿到表格，停止扩展样本页")
                break
            rows = self.parse_ths_rows(html)
            snapshot["samples"][page] = rows
            print(f"同花顺校验：page={page} 抓到 {len(rows)} 条样本")

        return snapshot

    def validate_against_ths(
        self, stocks_by_exchange: Dict[str, List[Dict[str, Any]]], snapshot: Dict[str, Any]
    ) -> bool:
        """使用同花顺网页总页数和样本代码名称对最终结果做一致性校验"""
        page_size = int(snapshot.get("page_size") or self.THS_PAGE_SIZE)
        total_pages = snapshot.get("total_pages")
        all_stocks = [
            stock
            for stocks in stocks_by_exchange.values()
            for stock in stocks
        ]
        stock_map = {stock["股票代码"]: stock for stock in all_stocks}
        total_count = len(stock_map)

        if total_pages:
            estimated_total = int(total_pages) * page_size
            print(
                "同花顺校验："
                f"网页总页数 {total_pages}，首个样本页抓到 {page_size} 条，"
                f"按此估算约 {estimated_total} 条；当前结果 {total_count}"
            )
            if abs(total_count - estimated_total) > 200:
                print("同花顺校验提示：总量与首屏估算差异较大，继续依赖样本行做严格校验")

        for page, rows in snapshot.get("samples", {}).items():
            missing_codes: List[str] = []
            mismatched_names: List[str] = []
            for row in rows:
                code = row["code"]
                expected_name = row["name"]
                stock = stock_map.get(code)
                if stock is None:
                    missing_codes.append(code)
                    continue
                actual_name = stock["股票名称"]
                if not self.stock_names_match(actual_name, expected_name):
                    mismatched_names.append(f"{code}:{stock['股票名称']}!={row['name']}")

            print(
                f"同花顺校验：page={page} 样本 {len(rows)} 条，"
                f"缺失 {len(missing_codes)}，名称不一致 {len(mismatched_names)}"
            )
            if missing_codes:
                print(f"同花顺校验失败：page={page} 缺失代码 {missing_codes[:10]}")
                return False
            if mismatched_names:
                if len(mismatched_names) > 2:
                    print(f"同花顺校验失败：page={page} 名称不一致 {mismatched_names[:10]}")
                    return False
                print(f"同花顺校验提示：page={page} 少量名称差异 {mismatched_names[:10]}")

        print("同花顺校验通过：网页样本与最终股票列表一致")
        return True

    def existing_stock_list_directory(self) -> Path:
        """优先使用真实 DataCenter/StockList 作为增量对比基线，避免临时目录误判全量新增。"""
        data_center = os.environ.get("STOCKMASTER_DATA_CENTER")
        if data_center:
            candidate = Path(data_center).expanduser() / "StockList"
            if candidate.exists():
                return candidate
        return Path(self.output_dir)

    def load_existing_stocks(self, exchange: str) -> Dict[str, Dict[str, Any]]:
        """加载已存在的股票信息"""
        if pd is None:
            raise RuntimeError("缺少 pandas 依赖")

        existing_stocks: Dict[str, Dict[str, Any]] = {}
        file_path = self.existing_stock_list_directory() / self.exchanges[exchange]["file"]

        try:
            if file_path.exists():
                df = pd.read_csv(file_path, encoding="utf-8-sig", dtype={"股票代码": str})
                for _, row in df.iterrows():
                    stock_code = str(row["股票代码"]).zfill(6)
                    existing_stocks[stock_code] = {
                        "股票名称": str(row.get("股票名称", "")),
                        "交易所": str(row.get("交易所", "")),
                        "交易所代码": str(row.get("交易所代码", "")),
                        "是否ST": int(row.get("是否ST", 0) or 0),
                    }
                print(
                    f"✓ 加载了 {len(existing_stocks)} 只已存在的 {exchange} 股票"
                    f"（基线目录: {file_path.parent}）"
                )
        except Exception as exc:
            print(f"加载已存在的 {exchange} 股票失败: {exc}")

        return existing_stocks

    def detect_changes(
        self,
        current_stocks: List[Dict[str, Any]],
        existing_stocks: Dict[str, Dict[str, Any]],
        exchange: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """检测股票变化（新上市、退市、信息更新）"""
        current_codes = {stock["股票代码"] for stock in current_stocks}
        existing_codes = set(existing_stocks.keys())

        changes: Dict[str, List[Dict[str, Any]]] = {
            "new_listings": [],
            "delistings": [],
            "updates": [],
        }

        for stock in current_stocks:
            if stock["股票代码"] in current_codes - existing_codes:
                changes["new_listings"].append(stock)

        for code in existing_codes - current_codes:
            changes["delistings"].append(
                {
                    "股票代码": code,
                    "股票名称": existing_stocks[code]["股票名称"],
                    "退市时间": datetime.now().strftime("%Y-%m-%d"),
                }
            )

        for stock in current_stocks:
            code = stock["股票代码"]
            if code not in existing_stocks:
                continue
            existing = existing_stocks[code]
            if (
                stock["股票名称"] != existing["股票名称"]
                or int(stock.get("是否ST", 0)) != int(existing.get("是否ST", 0))
            ):
                changes["updates"].append({"old": existing, "new": stock})

        print(
            f"✓ {exchange} 变化检测: 新上市 {len(changes['new_listings'])} 只, "
            f"退市 {len(changes['delistings'])} 只, 更新 {len(changes['updates'])} 只"
        )
        return changes

    def save_stocks_to_csv(self, stocks: List[Dict[str, Any]], exchange: str) -> None:
        """保存股票信息到 CSV 文件，保持固定字段顺序"""
        if pd is None:
            raise RuntimeError("缺少 pandas 依赖")

        if not stocks:
            print(f"没有 {exchange} 股票数据需要保存")
            return

        columns = ["股票代码", "股票名称", "交易所", "交易所代码", "是否ST"]
        df = pd.DataFrame(stocks)
        df["股票代码"] = df["股票代码"].astype(str).str.zfill(6)
        df["是否ST"] = df["是否ST"].astype(int)
        df = df[columns].sort_values("股票代码")
        file_path = os.path.join(self.output_dir, self.exchanges[exchange]["file"])
        df.to_csv(file_path, index=False, encoding="utf-8-sig")
        print(f"✓ {exchange} 股票信息已保存到: {file_path} ({len(df)} 只股票)")

    def save_changes_log(self, changes: Dict[str, List[Dict[str, Any]]], exchange: str) -> None:
        """输出变化信息到标准输出，供 App 日志面板实时展示"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n=== {timestamp} {exchange} 股票变化记录 ===")

        if changes["new_listings"]:
            print(f"新上市股票 ({len(changes['new_listings'])} 只):")
            for stock in changes["new_listings"]:
                print(f"  + {stock['股票代码']} {stock['股票名称']}")

        if changes["delistings"]:
            print(f"退市股票 ({len(changes['delistings'])} 只):")
            for stock in changes["delistings"]:
                print(f"  - {stock['股票代码']} {stock['股票名称']} (退市时间: {stock['退市时间']})")

        if changes["updates"]:
            print(f"信息更新 ({len(changes['updates'])} 只):")
            for update in changes["updates"]:
                print(
                    f"  ~ {update['new']['股票代码']} "
                    f"{update['old']['股票名称']} -> {update['new']['股票名称']}"
                )

    def get_summary_statistics(self) -> Dict[str, Any]:
        """获取股票统计信息"""
        if pd is None:
            raise RuntimeError("缺少 pandas 依赖")

        stats: Dict[str, Any] = {}
        total_stocks = 0
        for exchange, config in self.exchanges.items():
            file_path = os.path.join(self.output_dir, config["file"])
            try:
                if os.path.exists(file_path):
                    df = pd.read_csv(file_path, encoding="utf-8-sig", dtype={"股票代码": str})
                    count = len(df)
                else:
                    count = 0
                stats[exchange] = {
                    "name": config["name"],
                    "count": count,
                    "file": config["file"],
                }
                total_stocks += count
            except Exception as exc:
                print(f"读取 {exchange} 统计信息失败: {exc}")
                stats[exchange] = {
                    "name": config["name"],
                    "count": 0,
                    "file": config["file"],
                }

        stats["total"] = total_stocks
        return stats

    def collect_exchange_with_fallback(
        self,
        exchange: str,
        source_summary: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """先尝试东方财富，数量不可信时切换为 AkShare"""
        eastmoney_stocks = self.get_all_stocks_eastmoney(exchange)
        min_expected = int(self.exchanges[exchange]["min_expected"])

        if len(eastmoney_stocks) >= min_expected:
            source_summary[exchange] = "eastmoney"
            print(
                f"来源判定：{exchange} 东方财富结果 {len(eastmoney_stocks)} 只，"
                f"达到最小可信阈值 {min_expected}"
            )
            return eastmoney_stocks

        print(
            f"来源判定：{exchange} 东方财富结果仅 {len(eastmoney_stocks)} 只，"
            f"低于可信阈值 {min_expected}，切换 AkShare 重建"
        )
        akshare_stocks = self.get_exchange_stocks_akshare(exchange)
        source_summary[exchange] = "akshare"
        return akshare_stocks

    def persist_exchange_stocks(
        self,
        stocks_by_exchange: Dict[str, List[Dict[str, Any]]],
        enable_update: bool,
    ) -> Dict[str, bool]:
        """统一保存校验通过后的股票列表"""
        results: Dict[str, bool] = {}
        for exchange, stocks in stocks_by_exchange.items():
            try:
                if enable_update:
                    existing_stocks = self.load_existing_stocks(exchange)
                    changes = self.detect_changes(stocks, existing_stocks, exchange)
                    if any(changes.values()):
                        self.save_changes_log(changes, exchange)
                self.save_stocks_to_csv(stocks, exchange)
                results[exchange] = True
            except Exception as exc:
                print(f"保存 {exchange} 股票列表失败: {exc}")
                results[exchange] = False
        return results

    def fetch_exchange_stocks(self, exchange: str, enable_update: bool = True) -> bool:
        """获取指定交易所的股票信息"""
        try:
            print(f"\n🔍 开始获取 {self.exchanges[exchange]['name']} 股票信息...")
            source_summary: Dict[str, str] = {}
            ipo_candidates = self.collect_ipo_candidates()
            self.save_ipo_views(ipo_candidates)
            stocks = self.collect_exchange_with_fallback(exchange, source_summary)
            if not stocks:
                print(f"未能获取到 {exchange} 的股票信息")
                return False
            results = self.persist_exchange_stocks({exchange: stocks}, enable_update)
            print(f"✅ {exchange} 股票信息获取完成，最终来源: {source_summary.get(exchange)}")
            return results.get(exchange, False)
        except Exception as exc:
            print(f"获取 {exchange} 股票信息失败: {exc}")
            return False

    def fetch_all_stocks(self, enable_update: bool = True) -> Dict[str, bool]:
        """获取所有交易所的股票信息"""
        print("\n🚀 开始获取全市场股票信息...")
        print("=" * 60)

        source_summary: Dict[str, str] = {}
        stocks_by_exchange: Dict[str, List[Dict[str, Any]]] = {}
        ipo_candidates = self.collect_ipo_candidates()
        ipo_stats = self.save_ipo_views(ipo_candidates)

        for exchange in self.exchanges.keys():
            stocks_by_exchange[exchange] = self.collect_exchange_with_fallback(
                exchange, source_summary
            )
            time.sleep(0.5)

        ipo_additions = self.merge_recent_ipo_candidates(stocks_by_exchange, ipo_candidates)
        ipo_added_total = sum(len(items) for items in ipo_additions.values())
        if ipo_added_total > 0:
            for exchange, items in ipo_additions.items():
                if items:
                    source_summary[exchange] = f"{source_summary.get(exchange, 'unknown')}+recent-ipo"

        snapshot = self.fetch_ths_reference_snapshot(sample_pages=3)
        if snapshot and not self.validate_against_ths(stocks_by_exchange, snapshot):
            print("同花顺校验未通过，放弃混合来源结果，切换全市场 AkShare 重建")
            stocks_by_exchange = self.get_all_exchange_stocks_akshare()
            source_summary = {exchange: "akshare-rebuild" for exchange in self.exchanges.keys()}
            ipo_additions = self.merge_recent_ipo_candidates(stocks_by_exchange, ipo_candidates)
            for exchange, items in ipo_additions.items():
                if items:
                    source_summary[exchange] = f"{source_summary.get(exchange, 'unknown')}+recent-ipo"
            if snapshot and not self.validate_against_ths(stocks_by_exchange, snapshot):
                raise RuntimeError("AkShare 全市场重建后仍未通过同花顺网页校验")
        elif snapshot is None:
            print("同花顺校验：本次未拿到网页样本，仅按结构化源结果保存")

        results = self.persist_exchange_stocks(stocks_by_exchange, enable_update)

        print("\n📊 获取结果总结:")
        print("=" * 60)
        for exchange, success in results.items():
            status = "✅ 成功" if success else "❌ 失败"
            count = len(stocks_by_exchange.get(exchange, []))
            source = source_summary.get(exchange, "unknown")
            print(
                f"{self.exchanges[exchange]['name']}: {status} "
                f"({count} 只股票, 来源: {source})"
            )

        total_count = sum(len(items) for items in stocks_by_exchange.values())
        print(f"\n📈 总计: {total_count} 只A股股票")
        print(
            "🆕 IPO 视图: "
            f"已上市新股 {ipo_stats['listed']} 只, 待上市新股 {ipo_stats['pending']} 只"
        )
        print(f"💾 数据保存位置: {os.path.abspath(self.output_dir)}")
        return results


def main() -> None:
    """主函数"""
    print("🚀 全市场股票信息获取器")
    print("=" * 50)

    fetcher = AllStocksFetcher()
    fetcher.fetch_all_stocks(enable_update=True)
    stats = fetcher.get_summary_statistics()

    print("\n📈 股票统计信息:")
    print("=" * 50)
    for exchange, stat in stats.items():
        if exchange != "total":
            print(f"{stat['name']}: {stat['count']} 只股票")
    print(f"总计: {stats['total']} 只股票")


if __name__ == "__main__":
    main()
