#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import argparse
from datetime import datetime
import os
import random
import time

HELP_REQUESTED = any(arg in ("-h", "--help") for arg in sys.argv[1:])
try:
    import requests
    import pandas as pd
except ModuleNotFoundError:
    if not HELP_REQUESTED:
        raise
    requests = None
    pd = None

# Skill-local script path for importing real_time_stock_fetcher after script extraction.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
external_script_path = SCRIPT_DIR
sys.path.insert(0, external_script_path)

try:
    from real_time_stock_fetcher import RealStockDataFetcher
except ImportError:
    pass

def get_random_headers():
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    ]
    return {
        'User-Agent': random.choice(user_agents),
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive'
    }

def fetch_kline_eastmoney(code, days=250, start_date=None):
    """
    直接从东方财富获取K线数据 (备用/优先方案)
    """
    try:
        # 判断交易所
        # 深交所: 0, 上交所: 1
        # 000/001/002/003/300/301/920/43/83/87/92 → 深交所
        if code.startswith(('000', '001', '002', '003', '300', '301', '920', '43', '83', '87', '92')):
            market = '0'  # 深交所
        elif code.startswith(('8', '4')) and len(code) == 6:
            market = '0'  # 北交所/新三板 → 深交所编码
        else:
            market = '1'  # 上交所（600/601/603/605/688）
        
        url = 'http://push2his.eastmoney.com/api/qt/stock/kline/get'
        
        # 转换日期格式 YYYY-MM-DD -> YYYYMMDD
        beg_date = '0'
        if start_date:
            beg_date = start_date.replace('-', '')
            
        params = {
            'secid': f'{market}.{code}',
            'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
            'klt': '101',  # 日K线
            'fqt': '1',    # 前复权
            'beg': beg_date,
            'end': '20500101',
            'lmt': str(days) if not start_date else '10000' # 如果指定了开始日期，则不限制条数（设一个大值）
        }
        
        response = requests.get(url, params=params, headers=get_random_headers(), timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data'] and 'klines' in data['data']:
                klines = data['data']['klines']
                result = []
                for line in klines:
                    parts = line.split(',')
                    if len(parts) >= 11:
                        result.append({
                            '日期': parts[0],
                            '开盘价': float(parts[1]),
                            '收盘价': float(parts[2]),
                            '最高价': float(parts[3]),
                            '最低价': float(parts[4]),
                            '成交量': int(parts[5]),
                            '成交额': float(parts[6]),
                            '振幅': float(parts[7]),
                            '涨跌幅': float(parts[8]),
                            '涨跌额': float(parts[9]),
                            '换手率': float(parts[10])
                        })
                # 按日期倒序 (最新的在前)
                result.reverse()
                return result
    except Exception as e:
        pass
    return None

def fetch_snapshot(code):
    """
    获取股票实时快照数据（包含市值等信息）
    使用腾讯财经接口：http://qt.gtimg.cn/q=
    """
    # 前缀判断
    if code.startswith(('600', '601', '603', '605', '688')):
        prefix = 'sh'
    else:
        prefix = 'sz'
        
    full_code = f"{prefix}{code}"
    url = f"http://qt.gtimg.cn/q={full_code}"
    
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return None
            
        content = resp.text
        # 格式: v_sh600519="51~贵州茅台~600519~1700.00~..."
        if not content or '=' not in content:
            return None
        
        data_str = content.split('="')[1].strip('";\n')
        parts = data_str.split('~')
        
        if len(parts) < 46:
            return None
            
        # 解析数据
        # 30: 时间戳 (YYYYMMDDHHMMSS)
        date_str = parts[30][:8] # YYYYMMDD
        formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        
        info = {
            "code": code,
            "name": parts[1],
            "price": float(parts[3]) if parts[3] else 0.0,
            "prev_close": float(parts[4]) if parts[4] else 0.0,
            "open": float(parts[5]) if parts[5] else 0.0,
            "high": float(parts[33]) if parts[33] else 0.0,
            "low": float(parts[34]) if parts[34] else 0.0,
            "volume": float(parts[36]) * 100 if parts[36] else 0, # 手 -> 股
            "amount": float(parts[37]) * 10000 if parts[37] else 0, # 万 -> 元
            "turnover_rate": float(parts[38]) if parts[38] else 0.0,
            "pe_ttm": float(parts[39]) if parts[39] else 0.0,
            "circulating_market_cap": float(parts[44]) * 100000000 if parts[44] else 0.0, # 亿 -> 元
            "total_market_cap": float(parts[45]) * 100000000 if parts[45] else 0.0, # 亿 -> 元
            "pb": float(parts[46]) if parts[46] else 0.0,
            "date": formatted_date
        }
        
        # 计算涨跌幅
        if info["prev_close"] > 0:
            info["change_percent"] = (info["price"] - info["prev_close"]) / info["prev_close"] * 100
            info["change_amount"] = info["price"] - info["prev_close"]
        else:
            info["change_percent"] = 0.0
            info["change_amount"] = 0.0
            
        return info
        
    except Exception as e:
        return None

def main():
    parser = argparse.ArgumentParser(description='Fetch single stock detail data')
    parser.add_argument('--code', required=True, help='Stock code')
    parser.add_argument('--json', action='store_true', help='Output JSON')
    parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    args = parser.parse_args()
    
    result = {
        "success": False,
        "message": "",
        "info": None,
        "kline": []
    }
    
    try:
        # 1. 获取实时快照
        snapshot = fetch_snapshot(args.code)
        if snapshot:
            result["info"] = snapshot
        else:
            result["message"] = "Failed to fetch snapshot"
            
        # 2. 获取K线数据
        # 优先使用本地直接实现的 Eastmoney 接口，因为它更可靠且不依赖外部环境
        kline_data = fetch_kline_eastmoney(args.code, start_date=args.start_date)
        
        if not kline_data:
            # 如果直接获取失败，尝试使用外部脚本 (备用)
            try:
                if 'RealStockDataFetcher' in globals():
                    fetcher = RealStockDataFetcher(output_dir=os.path.join(external_script_path, "real_time_data"))
                    # 禁用日志
                    fetcher.logger.disabled = True
                    for handler in fetcher.logger.handlers:
                        fetcher.logger.removeHandler(handler)
                        
                    df = fetcher.get_stock_data(args.code, days=250)
                    
                    if df is not None and not df.empty:
                        if not pd.api.types.is_datetime64_any_dtype(df['日期']):
                            df['日期'] = pd.to_datetime(df['日期'])
                        df['日期'] = df['日期'].dt.strftime('%Y-%m-%d')
                        df = df.fillna(0)
                        kline_data = df.to_dict('records')
            except Exception as e:
                pass
        
        if kline_data:
            result["kline"] = kline_data
            result["success"] = True
            
            # 3. 数据合并逻辑：确保当天数据存在
            # 如果快照数据存在，且日期比K线最新日期新，则追加
            if snapshot and kline_data:
                latest_kline_date = kline_data[0]['日期'] # 假设倒序
                snapshot_date = snapshot['date']
                
                if snapshot_date > latest_kline_date:
                    # 构造当天的K线数据
                    today_kline = {
                        '日期': snapshot_date,
                        '开盘价': snapshot['open'],
                        '收盘价': snapshot['price'],
                        '最高价': snapshot['high'],
                        '最低价': snapshot['low'],
                        '成交量': snapshot['volume'],
                        '成交额': snapshot['amount'],
                        # 其他字段如果K线需要，可以设为0或估算
                        '涨跌幅': snapshot['change_percent'],
                        '涨跌额': snapshot['change_amount'],
                        '换手率': snapshot['turnover_rate']
                    }
                    # 插入到最前面
                    result["kline"].insert(0, today_kline)
        else:
            result["message"] = "Failed to fetch K-line data"
            
    except Exception as e:
        result["message"] = f"Unexpected error: {str(e)}"
        
    # 输出JSON
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
