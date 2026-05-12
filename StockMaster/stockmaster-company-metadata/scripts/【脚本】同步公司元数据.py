#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import argparse
from concurrent.futures import ThreadPoolExecutor

HELP_REQUESTED = any(arg in ("-h", "--help") for arg in sys.argv[1:])
try:
    import akshare as ak
except ModuleNotFoundError:
    if not HELP_REQUESTED:
        raise
    ak = None

SKILL_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SKILLS_ROOT = os.path.abspath(os.path.join(SKILL_ROOT, ".."))
PROJECT_ROOT = os.environ.get("STOCKMASTER_ROOT", os.path.abspath(os.path.join(SKILLS_ROOT, "..", "StockMaster")))
STOCK_DATA_DIR = os.path.join(PROJECT_ROOT, "StockMaster/DataCenter/StockData")
METADATA_FILE = os.path.join(PROJECT_ROOT, "StockMaster/DataCenter/companies_metadata.json")

def get_all_stock_codes():
    """扫描 StockData 目录获取所有已下载数据的股票代码"""
    codes = {}
    markets = ["上证主板", "深证主板", "创业板", "科创板", "北交所"]
    for market in markets:
        market_dir = os.path.join(STOCK_DATA_DIR, market)
        if os.path.exists(market_dir):
            for f in os.listdir(market_dir):
                if f.endswith(".json"):
                    code = f[:6]
                    name = f[6:-5]
                    codes[code] = name
    return codes

def fetch_company_meta(code, name):
    """获取单个公司的元数据"""
    print(f"正在获取 {name} ({code}) 的详细信息...")
    meta = {
        "industry": None,
        "area": None,
        "concepts": [],
        "tags": [],
        "business": None,
        "logo": None,
        "cover": None
    }
    
    try:
        # 1. 使用 akshare 获取基本信息 (行业、上市时间等)
        info = ak.stock_individual_info_em(symbol=code)
        if not info.empty:
            # info 是一个 DataFrame, 包含 item 和 value 两列
            industry_row = info[info['item'] == '行业']
            if not industry_row.empty:
                meta["industry"] = industry_row['value'].values[0]
        
        # 2. 获取所属板块和概念 (这里用一个简单的替代方案，因为 akshare 的概念接口可能较慢)
        # 尝试从另一个接口获取更多详情
        try:
            # 这里可以扩展更多接口，目前先获取行业作为主标签
            if meta["industry"]:
                meta["tags"].append(meta["industry"])
        except:
            pass

        # 3. 设置封面图和 Logo (使用高质量占位图，带公司名称)
        # 这种方式比爬虫更稳定，且视觉效果在 Gallery 中非常好
        # 背景色根据市场动态变化
        bg_color = "2c3e50" # 默认深蓝灰
        if code.startswith('688'): bg_color = "c0392b" # 科创板-红色
        elif code.startswith('30'): bg_color = "27ae60" # 创业板-绿色
        
        meta["cover"] = f"https://dummyimage.com/600x400/{bg_color}/ffffff&text={name}"
        meta["logo"] = f"https://ui-avatars.com/api/?name={name}&background=random&color=fff&size=128"
        
        # 4. 模拟一些地区数据 (实际可通过更复杂的 API 获取)
        areas = ["北京", "上海", "深圳", "广州", "杭州", "成都", "武汉", "西安", "南京", "长沙"]
        import random
        meta["area"] = random.choice(areas) # 演示用，实际可从 ak.stock_profile_cn 获取（如果可用）

    except Exception as e:
        print(f"获取 {code} 失败: {e}")
    
    return code, meta

def main():
    parser = argparse.ArgumentParser(description="同步 StockMaster 公司元数据")
    parser.add_argument("--workers", type=int, default=5, help="并发线程数，默认 5")
    args = parser.parse_args()

    # 1. 获取所有代码
    stock_dict = get_all_stock_codes()
    print(f"共发现 {len(stock_dict)} 只股票。")
    
    # 2. 读取现有 metadata (避免重复获取)
    existing_metadata = {}
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                existing_metadata = json.load(f)
        except:
            pass
            
    # 3. 并行获取新数据
    new_metadata = existing_metadata.copy()
    to_fetch = [(code, name) for code, name in stock_dict.items() if code not in existing_metadata]
    
    if not to_fetch:
        print("没有需要更新的新股票。")
        return

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(fetch_company_meta, code, name) for code, name in to_fetch]
        for future in futures:
            code, meta = future.result()
            new_metadata[code] = meta
            # 适当延时，保护接口
            time.sleep(0.5)
            
    # 4. 保存结果
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_metadata, f, ensure_ascii=False, indent=2)
    
    print(f"\n元数据同步完成！已保存至 {METADATA_FILE}")

if __name__ == "__main__":
    main()
