#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票数据更新脚本
功能：获取最新的股票交易数据，并将其插入到现有CSV文件的最前面
支持上交所(SSE)和深交所(SZSE)股票数据更新
"""

import os
import sys
import csv
import time
import json
from datetime import datetime, timedelta
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
from typing import List, Dict, Optional, Tuple

HELP_REQUESTED = any(arg in ("-h", "--help") for arg in sys.argv[1:])
try:
    import requests
    import pandas as pd
except ModuleNotFoundError:
    if not HELP_REQUESTED:
        raise
    requests = None
    pd = None

# 配置日志
handlers = [logging.StreamHandler()] if HELP_REQUESTED else [
    logging.FileHandler('update_stock_data.log', encoding='utf-8'),
    logging.StreamHandler()
]
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=handlers
)
logger = logging.getLogger(__name__)

class StockDataUpdater:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 数据源配置
        self.data_sources = {
            'sina': self._get_sina_data,
            'tencent': self._get_tencent_data,
            'eastmoney': self._get_eastmoney_data
        }
        
        # 统计信息
        self.stats = {
            'total_processed': 0,
            'successful_updates': 0,
            'failed_updates': 0,
            'skipped_files': 0
        }
    
    def _get_sina_data(self, stock_code: str) -> Optional[Dict]:
        """从新浪财经获取股票数据"""
        try:
            # 判断市场
            if stock_code.startswith('6'):
                symbol = f'sh{stock_code}'
            else:
                symbol = f'sz{stock_code}'
            
            url = f'http://hq.sinajs.cn/list={symbol}'
            response = self.session.get(url, timeout=10)
            response.encoding = 'gbk'
            
            if response.status_code == 200 and response.text:
                data_str = response.text.split('="')[1].split('";')[0]
                if data_str and data_str != 'N/A':
                    parts = data_str.split(',')
                    if len(parts) >= 32:
                        return {
                            'date': parts[30],  # 日期
                            'open': float(parts[1]) if parts[1] else 0,  # 开盘价
                            'high': float(parts[4]) if parts[4] else 0,  # 最高价
                            'low': float(parts[5]) if parts[5] else 0,   # 最低价
                            'close': float(parts[3]) if parts[3] else 0, # 收盘价
                            'volume': int(parts[8]) if parts[8] else 0,   # 成交量
                            'amount': float(parts[9]) if parts[9] else 0  # 成交额
                        }
        except Exception as e:
            logger.debug(f"新浪数据获取失败 {stock_code}: {e}")
        return None
    
    def _get_tencent_data(self, stock_code: str) -> Optional[Dict]:
        """从腾讯财经获取股票数据"""
        try:
            # 判断市场
            if stock_code.startswith('6'):
                symbol = f'sh{stock_code}'
            else:
                symbol = f'sz{stock_code}'
            
            url = f'http://qt.gtimg.cn/q={symbol}'
            response = self.session.get(url, timeout=10)
            response.encoding = 'gbk'
            
            if response.status_code == 200 and response.text:
                data_str = response.text.split('="')[1].split('";')[0]
                if data_str and data_str != 'N/A':
                    parts = data_str.split('~')
                    if len(parts) >= 50:
                        return {
                            'date': parts[30],  # 日期
                            'open': float(parts[5]) if parts[5] else 0,   # 开盘价
                            'high': float(parts[33]) if parts[33] else 0, # 最高价
                            'low': float(parts[34]) if parts[34] else 0,  # 最低价
                            'close': float(parts[3]) if parts[3] else 0,  # 收盘价
                            'volume': int(parts[6]) if parts[6] else 0,    # 成交量
                            'amount': float(parts[37]) if parts[37] else 0 # 成交额
                        }
        except Exception as e:
            logger.debug(f"腾讯数据获取失败 {stock_code}: {e}")
        return None
    
    def _get_eastmoney_data(self, stock_code: str) -> Optional[Dict]:
        """从东方财富获取股票数据"""
        try:
            # 判断市场
            if stock_code.startswith('6'):
                market = '1'
            else:
                market = '0'
            
            url = f'http://push2.eastmoney.com/api/qt/stock/get?secid={market}.{stock_code}&fields=f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f53,f54,f55,f56,f57,f58'
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('rc') == 0 and data.get('data'):
                    stock_data = data['data']
                    return {
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'open': float(stock_data.get('f46', 0)) / 100,   # 开盘价
                        'high': float(stock_data.get('f44', 0)) / 100,   # 最高价
                        'low': float(stock_data.get('f45', 0)) / 100,    # 最低价
                        'close': float(stock_data.get('f43', 0)) / 100,  # 收盘价
                        'volume': int(stock_data.get('f47', 0)),         # 成交量
                        'amount': float(stock_data.get('f48', 0))        # 成交额
                    }
        except Exception as e:
            logger.debug(f"东方财富数据获取失败 {stock_code}: {e}")
        return None
    
    def get_latest_stock_data(self, stock_code: str) -> Optional[Dict]:
        """获取最新股票数据，尝试多个数据源"""
        for source_name, source_func in self.data_sources.items():
            try:
                data = source_func(stock_code)
                if data and data.get('close', 0) > 0:
                    logger.debug(f"成功从{source_name}获取 {stock_code} 数据")
                    return data
            except Exception as e:
                logger.debug(f"{source_name}数据源失败 {stock_code}: {e}")
                continue
        
        logger.warning(f"所有数据源都无法获取 {stock_code} 的数据")
        return None
    
    def calculate_ma(self, prices: List[float], period: int) -> float:
        """计算移动平均线"""
        if len(prices) < period:
            return 0.0
        return sum(prices[:period]) / period
    
    def update_csv_file(self, file_path: str, new_data: Dict) -> bool:
        """更新CSV文件，将新数据插入到最前面"""
        try:
            # 检查文件是否存在且不为空
            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                return False
            
            if os.path.getsize(file_path) == 0:
                logger.warning(f"文件为空，跳过更新: {file_path}")
                self.stats['skipped_files'] += 1
                return True
            
            # 读取现有数据
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 检查文件是否有内容
            if not lines:
                logger.warning(f"文件内容为空，跳过更新: {file_path}")
                self.stats['skipped_files'] += 1
                return True
            
            # 分离头部注释和数据
            header_lines = []
            data_lines = []
            data_started = False
            
            for line in lines:
                if line.startswith('#') and not data_started:
                    header_lines.append(line)
                elif line.startswith('日期,') and not data_started:
                    data_started = True
                    data_lines.append(line)  # CSV头部
                elif data_started:
                    data_lines.append(line)
            
            # 检查数据格式是否正确
            if not data_lines:
                logger.warning(f"文件中没有找到数据行，跳过更新: {file_path}")
                self.stats['skipped_files'] += 1
                return True
            
            # 检查是否已有今天的数据
            today = datetime.now().strftime('%Y-%m-%d')
            if len(data_lines) > 1:
                first_data_line = data_lines[1].strip()
                if first_data_line and first_data_line.startswith(today):
                    logger.info(f"文件 {os.path.basename(file_path)} 已有今日数据，跳过更新")
                    self.stats['skipped_files'] += 1
                    return True
            
            # 读取现有数据用于计算MA
            existing_data = []
            for line in data_lines[1:]:  # 跳过头部
                if line.strip():
                    parts = line.strip().split(',')
                    if len(parts) >= 5:
                        try:
                            # 验证数据格式
                            close_price = float(parts[4])
                            if close_price > 0:  # 确保收盘价有效
                                existing_data.append({
                                    'close': close_price,
                                    'date': parts[0]
                                })
                        except (ValueError, IndexError) as e:
                            logger.debug(f"跳过无效数据行: {line.strip()}, 错误: {e}")
                            continue
            
            # 计算MA值
            close_prices = [new_data['close']] + [d['close'] for d in existing_data]
            ma5 = self.calculate_ma(close_prices, 5)
            ma10 = self.calculate_ma(close_prices, 10)
            ma60 = self.calculate_ma(close_prices, 60)
            ma80 = self.calculate_ma(close_prices, 80)
            ma100 = self.calculate_ma(close_prices, 100)
            ma135 = self.calculate_ma(close_prices, 135)
            ma233 = self.calculate_ma(close_prices, 233)
            
            # 构建新的数据行
            new_row = f"{new_data['date']},{new_data['open']},{new_data['high']},{new_data['low']},{new_data['close']},{new_data['volume']},{new_data['amount']},{ma5:.2f},{ma10:.2f},{ma60:.2f},{ma80:.2f},{ma100:.2f},{ma135:.2f},{ma233:.2f}\n"
            
            # 更新生成时间
            updated_header = []
            for line in header_lines:
                if line.startswith('# 生成时间:'):
                    updated_header.append(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                else:
                    updated_header.append(line)
            
            # 写入更新后的文件
            with open(file_path, 'w', encoding='utf-8') as f:
                # 写入头部注释
                if updated_header:
                    f.writelines(updated_header)
                # 写入CSV头部
                if data_lines:
                    f.write(data_lines[0])
                # 写入新数据
                f.write(new_row)
                # 写入现有数据
                if len(data_lines) > 1:
                    f.writelines(data_lines[1:])
            
            logger.info(f"成功更新文件: {os.path.basename(file_path)}")
            self.stats['successful_updates'] += 1
            return True
            
        except Exception as e:
            logger.error(f"更新文件失败 {file_path}: {e}")
            self.stats['failed_updates'] += 1
            return False
    
    def update_single_stock(self, file_path: str) -> bool:
        """更新单个股票文件"""
        try:
            # 从文件名提取股票代码
            filename = os.path.basename(file_path)
            parts = filename.split('_')
            
            # 验证文件名格式
            if len(parts) < 2 or not parts[0].isdigit():
                logger.warning(f"文件名格式异常，跳过: {filename}")
                self.stats['skipped_files'] += 1
                return True
            
            stock_code = parts[0]
            
            # 验证股票代码格式
            if len(stock_code) != 6:
                logger.warning(f"股票代码格式异常，跳过: {stock_code}")
                self.stats['skipped_files'] += 1
                return True
            
            logger.info(f"正在更新股票: {stock_code}")
            
            # 获取最新数据
            latest_data = self.get_latest_stock_data(stock_code)
            if not latest_data:
                logger.warning(f"无法获取股票 {stock_code} 的最新数据")
                self.stats['failed_updates'] += 1
                return False
            
            # 更新CSV文件
            success = self.update_csv_file(file_path, latest_data)
            self.stats['total_processed'] += 1
            
            return success
            
        except Exception as e:
            logger.error(f"处理股票文件失败 {file_path}: {e}")
            self.stats['failed_updates'] += 1
            self.stats['total_processed'] += 1
            return False
    
    def update_directory(self, directory: str, max_workers: int = 10) -> None:
        """批量更新目录中的所有股票文件"""
        if not os.path.exists(directory):
            logger.error(f"目录不存在: {directory}")
            return
        
        # 获取所有CSV文件
        csv_files = []
        for filename in os.listdir(directory):
            if filename.endswith('_真实数据.csv'):
                csv_files.append(os.path.join(directory, filename))
        
        if not csv_files:
            logger.warning(f"目录 {directory} 中没有找到股票数据文件")
            return
        
        logger.info(f"开始更新 {directory} 目录，共 {len(csv_files)} 个文件")
        
        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.update_single_stock, file_path): file_path 
                      for file_path in csv_files}
            
            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"处理文件异常 {file_path}: {e}")
                
                # 添加延迟避免请求过于频繁
                time.sleep(0.1)
    
    def print_statistics(self) -> None:
        """打印统计信息"""
        logger.info("\n=== 更新统计 ===")
        logger.info(f"总处理文件数: {self.stats['total_processed']}")
        logger.info(f"成功更新: {self.stats['successful_updates']}")
        logger.info(f"更新失败: {self.stats['failed_updates']}")
        logger.info(f"跳过文件: {self.stats['skipped_files']}")
        
        if self.stats['total_processed'] > 0:
            success_rate = (self.stats['successful_updates'] + self.stats['skipped_files']) / self.stats['total_processed'] * 100
            logger.info(f"成功率: {success_rate:.2f}%")

def main():
    parser = argparse.ArgumentParser(description='股票数据更新工具')
    parser.add_argument('--market', choices=['SSE', 'SZSE', 'ALL'], default='ALL',
                       help='选择更新的市场: SSE(上交所), SZSE(深交所), ALL(全部)')
    parser.add_argument('--workers', type=int, default=10,
                       help='并发线程数 (默认: 10)')
    parser.add_argument('--single', type=str,
                       help='更新单个股票文件路径')
    
    args = parser.parse_args()
    
    updater = StockDataUpdater()
    
    try:
        if args.single:
            # 更新单个文件
            if os.path.exists(args.single):
                updater.update_single_stock(args.single)
            else:
                logger.error(f"文件不存在: {args.single}")
        else:
            # 批量更新
            base_dir = 'real_time_data'
            
            if args.market in ['SSE', 'ALL']:
                sse_dir = os.path.join(base_dir, 'SSE')
                if os.path.exists(sse_dir):
                    logger.info("开始更新上交所(SSE)股票数据...")
                    updater.update_directory(sse_dir, args.workers)
                else:
                    logger.warning(f"SSE目录不存在: {sse_dir}")
            
            if args.market in ['SZSE', 'ALL']:
                szse_dir = os.path.join(base_dir, 'SZSE')
                if os.path.exists(szse_dir):
                    logger.info("开始更新深交所(SZSE)股票数据...")
                    updater.update_directory(szse_dir, args.workers)
                else:
                    logger.warning(f"SZSE目录不存在: {szse_dir}")
        
        # 打印统计信息
        updater.print_statistics()
        
    except KeyboardInterrupt:
        logger.info("\n用户中断操作")
    except Exception as e:
        logger.error(f"程序执行出错: {e}")
    finally:
        logger.info("股票数据更新完成")

if __name__ == '__main__':
    main()
