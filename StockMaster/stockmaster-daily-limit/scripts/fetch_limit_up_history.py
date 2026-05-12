#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json
import subprocess
import argparse
from datetime import datetime

SKILL_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SKILLS_ROOT = os.path.abspath(os.path.join(SKILL_ROOT, ".."))
PROJECT_ROOT = os.environ.get("STOCKMASTER_ROOT", os.path.abspath(os.path.join(SKILLS_ROOT, "..", "StockMaster")))
DATA_CENTER_DIR = os.path.join(PROJECT_ROOT, "StockMaster/DataCenter/StockData")
LIMIT_UP_DIR = os.path.join(PROJECT_ROOT, "StockMaster/DataCenter/LimitUp")
PYTHON_EXEC = os.environ.get("STOCKMASTER_PYTHON", os.path.join(PROJECT_ROOT, "venv/bin/python3"))
LIMIT_FETCHER_DIR = os.path.dirname(os.path.abspath(__file__))
LIMIT_FETCHER_SCRIPT = os.path.join(LIMIT_FETCHER_DIR, "smart_daily_limit_fetcher.py")

def resolve_single_stock_script():
    candidates = [
        os.environ.get("STOCKMASTER_FETCH_SINGLE_SCRIPT"),
        os.path.join(SKILLS_ROOT, "stockmaster-stock-history", "scripts", "fetch_single_stock.py"),
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return candidates[0] or candidates[1]

SINGLE_STOCK_SCRIPT = resolve_single_stock_script()

def run_command(cmd):
    """执行命令并返回输出"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        print(f"Stderr: {e.stderr}")
        return None

def fetch_limit_up_list(date_str):
    """获取指定日期的涨停列表（优先从本地缓存读取）"""
    cache_file = os.path.join(LIMIT_UP_DIR, f"{date_str}-涨停列表.json")
    
    # 1. 检查本地是否已有 JSON 缓存
    if os.path.exists(cache_file):
        print(f"发现本地缓存: {cache_file}，直接使用。")
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("success") and "stocks" in data:
                    return data["stocks"]
        except Exception as e:
            print(f"读取本地缓存失败: {e}")
    
    # 2. 如果没有缓存，则从网络拉取
    print(f"正在从网络获取 {date_str} 的涨停列表...")
    cmd = [PYTHON_EXEC, LIMIT_FETCHER_SCRIPT, "--date", date_str, "--json"]
    output = run_command(cmd)
    if not output:
        return []
    
    try:
        # 尝试从输出中提取 JSON
        start_idx = output.find('{')
        if start_idx == -1:
            return []
        
        json_str = output[start_idx:]
        data = json.loads(json_str)
        
        # 3. 将拉取到的结果保存到本地缓存
        if data.get("success") and "stocks" in data:
            os.makedirs(LIMIT_UP_DIR, exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"已保存涨停列表至缓存: {cache_file}")
            return data["stocks"]
    except Exception as e:
        print(f"解析涨停列表失败: {e}")
    
    return []

def merge_kline_data(old_data, new_data):
    """合并 K 线数据，原则：只增不减，按日期排重"""
    if not old_data:
        return new_data
    
    # 将旧数据转为字典，日期为键
    kline_dict = {item["日期"]: item for item in old_data.get("kline", [])}
    
    # 用新数据覆盖或增加
    for item in new_data.get("kline", []):
        kline_dict[item["日期"]] = item
    
    # 重新排序（日期倒序，最新的在前）
    sorted_klines = sorted(kline_dict.values(), key=lambda x: x["日期"], reverse=True)
    
    # 更新基本信息（以最新的为准）
    merged = new_data.copy()
    merged["kline"] = sorted_klines
    if not merged.get("info") and old_data.get("info"):
        merged["info"] = old_data["info"]
        
    return merged

def get_market_folder(code):
    """根据股票代码判断市场分类目录"""
    if code.startswith('688'):
        return "科创板"
    elif code.startswith('60'):
        return "上证主板"
    elif code.startswith('30'):
        return "创业板"
    elif code.startswith(('000', '001', '002', '003')):
        return "深证主板"
    elif code.startswith(('8', '4')):
        return "北交所"
    return "其他"

def process_stock(stock_code, start_date="2019-10-01"):
    """处理单个股票的数据获取与合并"""
    # 1. 获取最新数据以取得股票名称
    print(f"正在处理股票: {stock_code}...")
    cmd = [PYTHON_EXEC, SINGLE_STOCK_SCRIPT, "--code", stock_code, "--start-date", start_date, "--json"]
    output = run_command(cmd)
    if not output:
        print(f"获取 {stock_code} 数据失败")
        return
    
    try:
        new_data = json.loads(output)
        if not new_data.get("success"):
            print(f"脚本返回失败: {new_data.get('message')}")
            return
            
        # 获取股票名称
        stock_name = "未知"
        if new_data.get("info") and new_data["info"].get("name"):
            stock_name = new_data["info"]["name"]
        
        # 确定存储路径：数据中心/StockData/市场目录/代码+名字.json
        market_folder = get_market_folder(stock_code)
        target_dir = os.path.join(DATA_CENTER_DIR, market_folder)
        file_path = os.path.join(target_dir, f"{stock_code}{stock_name}.json")
        
        # 2. 如果存在旧数据（可能在旧位置或新位置），进行合并
        old_data = None
        # 优先检查新位置
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
        else:
            # 检查旧格式位置 (002261-History.json)
            old_path = os.path.join(DATA_CENTER_DIR, f"{stock_code}-History.json")
            if os.path.exists(old_path):
                with open(old_path, 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
                # 读取后删除旧文件，准备迁移到新位置
                os.remove(old_path)

        if old_data:
            final_data = merge_kline_data(old_data, new_data)
            print(f"已合并旧数据并分类至 {market_folder}，当前总记录数: {len(final_data['kline'])}")
        else:
            final_data = new_data
            print(f"创建新文件并分类至 {market_folder}，记录数: {len(final_data['kline'])}")
            
        # 3. 保存数据
        os.makedirs(target_dir, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"处理 {stock_code} 过程中出错: {e}")

def main():
    parser = argparse.ArgumentParser(description='根据涨停列表拉取股票历史数据')
    parser.add_argument('--date', help='涨停日期 (YYYY-MM-DD)，默认为今天')
    args = parser.parse_args()
    
    target_date = args.date if args.date else datetime.now().strftime('%Y-%m-%d')
    
    # 1. 获取涨停列表
    stocks = fetch_limit_up_list(target_date)
    if not stocks:
        print(f"未找到 {target_date} 的涨停股票。")
        return
    
    print(f"共找到 {len(stocks)} 只涨停股票。")
    
    # 2. 逐个处理
    for stock in stocks:
        code = stock.get("code")
        if code:
            process_stock(code)
            
    print("\n任务全部完成！数据已同步至数据中心。")

if __name__ == "__main__":
    main()
