#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ST股票实时获取器
通过东方财富API实时获取所有ST股票信息

功能特点：
1. 实时获取所有ST股票（包括*ST、ST、PT等特殊处理股票）
2. 支持定期更新ST股票列表
3. 保存为CSV格式，与现有股票列表格式一致
4. 包含日志记录和错误处理机制
5. 统计并报告获取到的ST股票数量
"""

import sys
HELP_REQUESTED = any(arg in ("-h", "--help") for arg in sys.argv[1:])
try:
    import requests
    import pandas as pd
except ModuleNotFoundError:
    if not HELP_REQUESTED:
        raise
    requests = None
    pd = None
import json
import time
import os
import re
import random
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

class STStocksFetcher:
    """ST股票获取器"""
    
    def __init__(self, output_dir: str = "."):
        self.output_dir = output_dir
        self.output_file = os.path.join(output_dir, "st_stocks.csv")
        self.ensure_output_dir()
        
        # API配置
        self.api_config = {
            'eastmoney_base': 'http://push2.eastmoney.com/api/qt/clist/get',
            'timeout': 15,
            'max_retries': 3,
            'retry_delay': 2
        }
        
        # 请求头配置 - 模拟真实浏览器
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'http://quote.eastmoney.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # 备用请求头列表
        self.backup_headers = [
            {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Referer': 'http://finance.sina.com.cn/stock/',
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Connection': 'keep-alive'
            },
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
                'Referer': 'http://quote.eastmoney.com/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
                'Connection': 'keep-alive'
            }
        ]
        
    def ensure_output_dir(self):
        """确保输出目录存在"""
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
    def log_message(self, message: str, level: str = "INFO"):
        """记录日志信息"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        
    def is_st_stock(self, stock_name: str) -> bool:
        """判断是否为ST股票"""
        if not stock_name:
            return False
            
        # ST股票的标识模式
        st_patterns = [
            r'^\*ST',      # *ST开头
            r'^ST',        # ST开头
            r'^PT',        # PT开头（特别转让）
            r'\*ST',       # 包含*ST
            r'ST.*',       # 包含ST
        ]
        
        for pattern in st_patterns:
            if re.search(pattern, stock_name, re.IGNORECASE):
                return True
                
        return False
        
    def validate_stock_code(self, stock_code: str) -> bool:
        """验证股票代码格式"""
        if not stock_code or len(stock_code) != 6:
            return False
            
        try:
            # 确保是6位数字
            int(stock_code)
        except ValueError:
            return False
            
        # A股股票代码范围
        # 上交所：60、68开头
        # 深交所：00、30开头
        # 北交所：43、83、87开头
        return stock_code.startswith(('60', '68', '00', '30', '43', '83', '87'))
        
    def make_request_with_retry(self, url: str, headers: dict = None, max_retries: int = 3) -> requests.Response:
        """带重试机制的请求方法"""
        if headers is None:
            headers = self.headers
            
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                # 随机延时，避免被识别为机器人
                if attempt > 0:
                    delay = random.uniform(1, 3) + attempt * 0.5
                    time.sleep(delay)
                    
                # 如果不是第一次尝试，使用备用请求头
                if attempt > 0 and self.backup_headers:
                    headers = random.choice(self.backup_headers)
                    self.log_message(f"第{attempt + 1}次尝试，使用备用请求头")
                    
                response = requests.get(url, headers=headers, timeout=15)
                
                # 检查响应状态
                if response.status_code == 200:
                    return response
                elif response.status_code == 403:
                    self.log_message(f"第{attempt + 1}次请求被拒绝 (403 Forbidden): {url}", "WARN")
                    if attempt < max_retries - 1:
                        continue
                else:
                    response.raise_for_status()
                    
            except requests.exceptions.RequestException as e:
                last_exception = e
                self.log_message(f"第{attempt + 1}次请求失败: {e}", "ERROR")
                if attempt < max_retries - 1:
                    continue
                    
        # 所有重试都失败了
        if last_exception:
            raise last_exception
        else:
            raise requests.exceptions.RequestException(f"请求失败，已重试{max_retries}次")
            
    def get_st_stocks_from_eastmoney(self) -> List[Dict]:
        """从东方财富API获取所有ST股票"""
        st_stocks = []
        seen_codes = set()  # 用于去重
        
        try:
            self.log_message("开始从东方财富API获取ST股票列表...")
            
            # 分别获取上交所、深交所、北交所的ST股票
            exchanges_config = [
                {'name': '上海证券交易所', 'fs': 'm:1+t:2,m:1+t:23'},  # 上交所主板+科创板
                {'name': '深圳证券交易所', 'fs': 'm:0+t:6,m:0+t:13,m:0+t:80'},  # 深交所主板+中小板+创业板
                {'name': '北京证券交易所', 'fs': 'm:0+t:81+s:2048'}  # 北交所正常交易股票
            ]
            
            for exchange_config in exchanges_config:
                exchange_name = exchange_config['name']
                fs_param = exchange_config['fs']
                
                self.log_message(f"正在获取{exchange_name}的ST股票...")
                
                page = 1
                page_size = 100
                exchange_st_count = 0
                
                while True:
                    try:
                        # 构建API请求参数
                        params = {
                            'pn': page,
                            'pz': page_size,
                            'po': '1',
                            'np': '1',
                            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
                            'fltt': '2',
                            'invt': '2',
                            'fid': 'f3',
                            'fs': fs_param,
                            'fields': 'f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f26'
                        }
                        
                        # 构建完整URL
                        import urllib.parse
                        full_url = f"{self.api_config['eastmoney_base']}?{urllib.parse.urlencode(params)}"
                        
                        response = self.make_request_with_retry(full_url)
                        data = response.json()
                        
                        # 检查响应数据结构
                        if 'data' not in data or not data['data']:
                            break
                            
                        # 获取股票列表
                        if 'diff' not in data['data'] or not data['data']['diff']:
                            break
                            
                        stock_list = data['data']['diff']
                        current_page_st_count = 0
                        
                        for stock in stock_list:
                            try:
                                stock_code = stock.get('f12', '')
                                stock_name = stock.get('f14', '')
                                
                                # 验证股票代码格式
                                if not self.validate_stock_code(stock_code):
                                    continue
                                    
                                # 检查是否为ST股票
                                if not self.is_st_stock(stock_name):
                                    continue
                                    
                                if stock_code and stock_name and stock_code not in seen_codes:
                                    seen_codes.add(stock_code)
                                    
                                    # 添加ST股票信息
                                    stock_info = {
                                        '股票代码': stock_code,
                                        '股票名称': stock_name,
                                        '交易所': exchange_name,
                                        '股票类型': self.get_st_type(stock_name),
                                        '获取时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    }
                                    
                                    st_stocks.append(stock_info)
                                    current_page_st_count += 1
                                    exchange_st_count += 1
                                    
                            except Exception as e:
                                self.log_message(f"解析股票信息失败: {e}", "ERROR")
                                continue
                        
                        if current_page_st_count > 0:
                            self.log_message(f"✓ {exchange_name} 第{page}页获取了 {current_page_st_count} 只ST股票")
                        
                        # 检查是否还有更多数据
                        if len(stock_list) < page_size:
                            break
                            
                        page += 1
                        
                        # 避免请求过于频繁
                        time.sleep(0.8)
                        
                        # 安全检查：避免无限循环
                        if page > 50:  # 最多50页
                            self.log_message(f"已达到最大页数限制(50页)，停止获取", "WARN")
                            break
                            
                    except Exception as e:
                        self.log_message(f"获取{exchange_name}第{page}页数据失败: {e}", "ERROR")
                        break
                        
                self.log_message(f"🎉 {exchange_name} 共获取了 {exchange_st_count} 只ST股票")
                
        except Exception as e:
            self.log_message(f"获取ST股票列表失败: {e}", "ERROR")
            
        return st_stocks
        
    def get_st_type(self, stock_name: str) -> str:
        """获取ST股票的具体类型"""
        if not stock_name:
            return "未知"
            
        if stock_name.startswith('*ST'):
            return "*ST股票"
        elif stock_name.startswith('ST'):
            return "ST股票"
        elif stock_name.startswith('PT'):
            return "PT股票"
        elif '*ST' in stock_name:
            return "*ST股票"
        elif 'ST' in stock_name:
            return "ST股票"
        else:
            return "特殊处理股票"
            
    def save_to_csv(self, st_stocks: List[Dict]) -> bool:
        """保存ST股票数据到CSV文件"""
        try:
            if not st_stocks:
                self.log_message("没有ST股票数据需要保存", "WARN")
                return False
                
            # 创建DataFrame
            df = pd.DataFrame(st_stocks)
            
            # 按股票代码排序
            df = df.sort_values('股票代码')
            
            # 保存到CSV文件
            df.to_csv(self.output_file, index=False, encoding='utf-8-sig')
            
            self.log_message(f"✓ ST股票数据已保存到: {self.output_file}")
            self.log_message(f"✓ 文件大小: {os.path.getsize(self.output_file)} 字节")
            
            return True
            
        except Exception as e:
            self.log_message(f"保存ST股票数据失败: {e}", "ERROR")
            return False
            
    def load_existing_st_stocks(self) -> List[Dict]:
        """加载已存在的ST股票数据"""
        existing_stocks = []
        
        try:
            if os.path.exists(self.output_file):
                df = pd.read_csv(self.output_file, encoding='utf-8-sig')
                existing_stocks = df.to_dict('records')
                self.log_message(f"✓ 加载了 {len(existing_stocks)} 只已存在的ST股票")
        except Exception as e:
            self.log_message(f"加载已存在的ST股票失败: {e}", "ERROR")
            
        return existing_stocks
        
    def update_st_stocks(self) -> Dict:
        """更新ST股票列表"""
        result = {
            'success': False,
            'total_count': 0,
            'new_count': 0,
            'removed_count': 0,
            'message': ''
        }
        
        try:
            self.log_message("开始更新ST股票列表...")
            
            # 获取最新的ST股票数据
            current_st_stocks = self.get_st_stocks_from_eastmoney()
            
            if not current_st_stocks:
                result['message'] = "未获取到ST股票数据"
                return result
                
            # 加载已存在的ST股票数据
            existing_st_stocks = self.load_existing_st_stocks()
            existing_codes = {stock['股票代码'] for stock in existing_st_stocks}
            current_codes = {stock['股票代码'] for stock in current_st_stocks}
            
            # 计算变化
            new_codes = current_codes - existing_codes
            removed_codes = existing_codes - current_codes
            
            # 保存最新数据
            if self.save_to_csv(current_st_stocks):
                result['success'] = True
                result['total_count'] = len(current_st_stocks)
                result['new_count'] = len(new_codes)
                result['removed_count'] = len(removed_codes)
                
                # 生成统计报告
                message_parts = []
                message_parts.append(f"ST股票总数: {result['total_count']}")
                
                if new_codes:
                    new_stocks = [stock for stock in current_st_stocks if stock['股票代码'] in new_codes]
                    message_parts.append(f"新增ST股票: {len(new_codes)}只")
                    for stock in new_stocks[:5]:  # 只显示前5只
                        message_parts.append(f"  + {stock['股票代码']} {stock['股票名称']}")
                    if len(new_stocks) > 5:
                        message_parts.append(f"  + ... 还有{len(new_stocks) - 5}只")
                        
                if removed_codes:
                    message_parts.append(f"移除ST股票: {len(removed_codes)}只")
                    for code in list(removed_codes)[:5]:  # 只显示前5只
                        message_parts.append(f"  - {code}")
                    if len(removed_codes) > 5:
                        message_parts.append(f"  - ... 还有{len(removed_codes) - 5}只")
                        
                if not new_codes and not removed_codes:
                    message_parts.append("ST股票列表无变化")
                    
                result['message'] = '\n'.join(message_parts)
                
            else:
                result['message'] = "保存ST股票数据失败"
                
        except Exception as e:
            result['message'] = f"更新ST股票列表失败: {e}"
            self.log_message(result['message'], "ERROR")
            
        return result
        
    def get_statistics(self) -> Dict:
        """获取ST股票统计信息"""
        stats = {
            'total_count': 0,
            'by_exchange': {},
            'by_type': {},
            'file_info': {},
            'last_update': None
        }
        
        try:
            if os.path.exists(self.output_file):
                # 读取文件信息
                file_stat = os.stat(self.output_file)
                stats['file_info'] = {
                    'path': self.output_file,
                    'size': file_stat.st_size,
                    'modified': datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # 读取股票数据
                df = pd.read_csv(self.output_file, encoding='utf-8-sig')
                stats['total_count'] = len(df)
                
                # 按交易所统计
                if '交易所' in df.columns:
                    stats['by_exchange'] = df['交易所'].value_counts().to_dict()
                    
                # 按股票类型统计
                if '股票类型' in df.columns:
                    stats['by_type'] = df['股票类型'].value_counts().to_dict()
                    
                # 获取最后更新时间
                if '获取时间' in df.columns and len(df) > 0:
                    stats['last_update'] = df['获取时间'].iloc[0]
                    
        except Exception as e:
            self.log_message(f"获取ST股票统计信息失败: {e}", "ERROR")
            
        return stats

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ST股票实时获取器')
    parser.add_argument('--update', action='store_true', help='更新ST股票列表')
    parser.add_argument('--stats', action='store_true', help='显示ST股票统计信息')
    parser.add_argument('--output-dir', default='.', help='输出目录（默认为当前目录）')
    
    args = parser.parse_args()
    
    # 创建ST股票获取器
    fetcher = STStocksFetcher(output_dir=args.output_dir)
    
    if args.stats:
        # 显示统计信息
        stats = fetcher.get_statistics()
        
        print("\n=== ST股票统计信息 ===")
        print(f"ST股票总数: {stats['total_count']}")
        
        if stats['by_exchange']:
            print("\n按交易所分布:")
            for exchange, count in stats['by_exchange'].items():
                print(f"  {exchange}: {count}只")
                
        if stats['by_type']:
            print("\n按股票类型分布:")
            for stock_type, count in stats['by_type'].items():
                print(f"  {stock_type}: {count}只")
                
        if stats['file_info']:
            print(f"\n文件信息:")
            print(f"  路径: {stats['file_info']['path']}")
            print(f"  大小: {stats['file_info']['size']} 字节")
            print(f"  修改时间: {stats['file_info']['modified']}")
            
        if stats['last_update']:
            print(f"  最后更新: {stats['last_update']}")
            
    elif args.update:
        # 更新ST股票列表
        result = fetcher.update_st_stocks()
        
        print("\n=== ST股票更新结果 ===")
        if result['success']:
            print("✓ 更新成功")
        else:
            print("✗ 更新失败")
            
        print(result['message'])
        
    else:
        # 默认执行更新操作
        result = fetcher.update_st_stocks()
        
        print("\n=== ST股票获取结果 ===")
        if result['success']:
            print("✓ 获取成功")
        else:
            print("✗ 获取失败")
            
        print(result['message'])

if __name__ == '__main__':
    main()
