#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

"""
A股涨停板数据智能获取脚本 - 自动交易日判断版本
功能：智能判断当前日期是否为交易日，如果不是则自动获取前一个交易日的涨停数据
作者：AI助手
创建时间：2025-01-16
优化说明：基于daily_limit_fetcher_real.py，增加智能交易日判断功能
"""

import os
import sys
import logging
from datetime import datetime, date, timedelta
import time
import json
import glob
import shutil
import re
import argparse
from typing import Optional, List, Dict, Tuple

HELP_REQUESTED = any(arg in ("-h", "--help") for arg in sys.argv[1:])
try:
    import akshare as ak
    import pandas as pd
except ModuleNotFoundError:
    if not HELP_REQUESTED:
        raise
    ak = None
    pd = None

SKILL_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SKILLS_ROOT = os.path.abspath(os.path.join(SKILL_ROOT, ".."))
STOCKMASTER_ROOT = os.environ.get("STOCKMASTER_ROOT", os.path.abspath(os.path.join(SKILLS_ROOT, "..", "StockMaster")))
SCRIPT_LOG_DIR = os.environ.get("STOCKMASTER_SCRIPT_LOG_DIR", os.path.join(SKILL_ROOT, "logs"))
if not HELP_REQUESTED:
    os.makedirs(SCRIPT_LOG_DIR, exist_ok=True)

log_handlers = [logging.StreamHandler()]
if not HELP_REQUESTED:
    try:
        log_handlers.insert(0, logging.FileHandler(os.path.join(SCRIPT_LOG_DIR, 'smart_stock_fetcher.log')))
    except OSError:
        pass

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger(__name__)

# 配置参数
OBSIDIAN_VAULT_PATH = os.environ.get("STOCKMASTER_OBSIDIAN_VAULT_PATH", os.path.abspath(os.path.join(SKILLS_ROOT, "..", "ap-ob-notes")))
STOCK_DATA_PATH = f"{OBSIDIAN_VAULT_PATH}/Life/Stock/Company/Stock"
LIMIT_UP_PATH = f"{OBSIDIAN_VAULT_PATH}/Life/Stock/Company/Stock/涨停"
PLATE_PATH = f"{OBSIDIAN_VAULT_PATH}/Life/Stock/Company/Plate"
INDUSTRY_PLATE_PATH = f"{PLATE_PATH}/行业板块"
CONCEPT_PLATE_PATH = f"{PLATE_PATH}/概念板块"

# 数据质量阈值配置
MIN_EXPECTED_LIMIT_UP_COUNT = 10  # 正常交易日预期最少涨停股票数量
MAX_RETRY_ATTEMPTS = 3  # 最大重试次数
RETRY_DELAY = 2  # 重试延迟（秒）

class DataSourceInfo:
    """数据源信息类"""
    def __init__(self, name: str, function_name: str, description: str, reliability: int):
        self.name = name
        self.function_name = function_name
        self.description = description
        self.reliability = reliability  # 可靠性评分 1-10
        self.success_count = 0
        self.failure_count = 0
        self.last_success_time = None
        self.last_failure_time = None
    
    def record_success(self):
        self.success_count += 1
        self.last_success_time = datetime.now()
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now()
    
    def get_success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
    
    def get_quality_score(self) -> float:
        """计算数据源质量评分"""
        success_rate = self.get_success_rate()
        return (self.reliability * 0.6 + success_rate * 10 * 0.4)

# 定义多个数据源
DATA_SOURCES = [
    DataSourceInfo("东方财富涨停池", "stock_zt_pool_em", "东方财富网涨停股票池，包含历史涨停数据", 8),
    DataSourceInfo("东方财富强势涨停", "stock_zt_pool_strong_em", "东方财富网强势涨停股票池，质量较高", 9),
    DataSourceInfo("东方财富次新涨停", "stock_zt_pool_sub_new_em", "东方财富网次新股涨停池", 7),
    DataSourceInfo("东方财富涨停统计", "stock_zt_pool_dtgc_em", "东方财富网涨停股票统计数据", 8),
]

def is_trading_day(check_date: date) -> bool:
    """
    判断指定日期是否为交易日
    
    Args:
        check_date: 要检查的日期
    
    Returns:
        bool: 是否为交易日
    """
    # 检查是否为周末
    if check_date.weekday() >= 5:  # 周六(5)和周日(6)
        return False
    
    # 简单的节假日判断（可以根据需要扩展）
    # 这里只做基本的周末判断，实际应用中可以集成更完整的节假日数据
    
    # 检查是否为元旦
    if check_date.month == 1 and check_date.day == 1:
        return False
    
    # 检查是否为春节期间（简化版本，实际需要根据年份调整）
    # 这里只是示例，实际应用中需要更精确的节假日判断
    
    return True

def get_latest_trading_date(reference_date: date = None) -> date:
    """
    获取最近的交易日
    
    Args:
        reference_date: 参考日期，默认为当前日期
    
    Returns:
        date: 最近的交易日
    """
    if reference_date is None:
        reference_date = date.today()
    
    current_date = reference_date
    max_lookback_days = 10  # 最多向前查找10天
    
    for i in range(max_lookback_days):
        if is_trading_day(current_date):
            logger.info(f"找到最近的交易日: {current_date}")
            if current_date != reference_date:
                logger.info(f"从参考日期 {reference_date} 回退到交易日 {current_date}")
            return current_date
        
        # 向前回退一天
        current_date = current_date - timedelta(days=1)
        logger.debug(f"检查日期 {current_date}，不是交易日，继续回退")
    
    # 如果找不到交易日，返回参考日期的前一个工作日
    logger.warning(f"在{max_lookback_days}天内未找到交易日，使用默认逻辑")
    fallback_date = reference_date
    while fallback_date.weekday() >= 5:  # 至少避开周末
        fallback_date = fallback_date - timedelta(days=1)
    
    return fallback_date

def get_smart_trading_date(date_str=None) -> Tuple[date, str]:
    """
    智能获取交易日期
    
    Args:
        date_str (str, optional): 指定日期字符串，格式为YYYY-MM-DD
    
    Returns:
        Tuple[date, str]: (实际使用的日期, 日期选择说明)
    """
    if date_str:
        try:
            # 解析指定的日期
            specified_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # 获取当前日期
            today = date.today()
            
            # 检查是否为未来日期
            if specified_date > today:
                logger.error(f"❌ 不能查询未来日期: {specified_date}")
                logger.error(f"当前日期: {today}，查询日期: {specified_date}")
                raise ValueError(f"不能查询未来日期: {specified_date}，akshare只能获取历史数据")
            
            # 检查指定日期是否为交易日
            if is_trading_day(specified_date):
                logger.info(f"✓ 指定日期 {specified_date} 是交易日，直接使用")
                return specified_date, f"使用指定的交易日: {specified_date}"
            else:
                # 指定日期不是交易日，获取前一个交易日
                actual_date = get_latest_trading_date(specified_date)
                logger.warning(f"⚠ 指定日期 {specified_date} 不是交易日，自动调整为前一个交易日: {actual_date}")
                return actual_date, f"指定日期 {specified_date} 非交易日，自动调整为: {actual_date}"
            
        except ValueError as e:
            if "不能查询未来日期" in str(e):
                raise e
            logger.error(f"日期格式错误: {date_str}，请使用YYYY-MM-DD格式")
            raise ValueError(f"日期格式错误: {date_str}，请使用YYYY-MM-DD格式")
    else:
        # 未指定日期，智能获取最近的交易日
        today = date.today()
        
        if is_trading_day(today):
            logger.info(f"✓ 今天 {today} 是交易日，直接获取当天数据")
            return today, f"今天是交易日，获取当天数据: {today}"
        else:
            # 今天不是交易日，获取最近的交易日
            actual_date = get_latest_trading_date(today)
            logger.info(f"✓ 今天 {today} 不是交易日，自动获取最近的交易日: {actual_date}")
            return actual_date, f"今天非交易日，自动获取最近交易日: {actual_date}"

def try_data_source(source: DataSourceInfo, date_str: str) -> Tuple[Optional[pd.DataFrame], str]:
    """尝试从指定数据源获取数据"""
    try:
        logger.info(f"尝试使用数据源: {source.name} ({source.function_name})")
        
        # 根据不同的接口调用不同的函数
        if source.function_name == "stock_zt_pool_em":
            df = ak.stock_zt_pool_em(date=date_str)
        elif source.function_name == "stock_zt_pool_strong_em":
            df = ak.stock_zt_pool_strong_em(date=date_str)
        elif source.function_name == "stock_zt_pool_sub_new_em":
            df = ak.stock_zt_pool_sub_new_em(date=date_str)
        elif source.function_name == "stock_zt_pool_dtgc_em":
            df = ak.stock_zt_pool_dtgc_em(date=date_str)
        else:
            logger.warning(f"未知的数据源函数: {source.function_name}")
            return None, f"未知的数据源函数: {source.function_name}"
        
        if df is not None and not df.empty:
            logger.info(f"✓ {source.name} 成功获取 {len(df)} 条数据")
            source.record_success()
            return df, f"成功从{source.name}获取{len(df)}条数据"
        else:
            logger.warning(f"⚠ {source.name} 返回空数据")
            source.record_failure()
            return None, f"{source.name}返回空数据"
            
    except Exception as e:
        logger.warning(f"✗ {source.name} 获取失败: {type(e).__name__}: {e}")
        source.record_failure()
        return None, f"{source.name}获取失败: {str(e)}"

def get_stock_market_info(stock_code: str) -> Dict[str, str]:
    """根据股票代码识别市场和板块信息"""
    code = stock_code.strip()
    
    # 科创板（688开头）
    if code.startswith('688'):
        return {'market': 'SSE', 'board': 'STAR', 'limit_rate': 20.0, 'description': '上交所科创板'}
    
    # 上交所主板（60开头，但不是688）
    elif code.startswith('60'):
        return {'market': 'SSE', 'board': 'MAIN', 'limit_rate': 10.0, 'description': '上交所主板'}
    
    # 深交所主板（00开头）
    elif code.startswith('00'):
        return {'market': 'SZSE', 'board': 'MAIN', 'limit_rate': 10.0, 'description': '深交所主板'}
    
    # 深交所创业板（30开头）
    elif code.startswith('30'):
        return {'market': 'SZSE', 'board': 'GEM', 'limit_rate': 20.0, 'description': '深交所创业板'}
    
    # 北交所（8或4开头）
    elif code.startswith('8') or code.startswith('4'):
        return {'market': 'BSE', 'board': 'MAIN', 'limit_rate': 30.0, 'description': '北交所'}
    
    # 默认情况（包括其他代码）
    else:
        return {'market': 'UNKNOWN', 'board': 'UNKNOWN', 'limit_rate': 10.0, 'description': '未知市场'}

def is_st_stock(stock_name: str) -> bool:
    """判断是否为ST股票"""
    if not stock_name:
        return False
    
    # 移除单独的'S'前缀，避免误判正常以S开头的股票
    # 正确的ST股票前缀应该是完整的标识
    st_prefixes = ['*ST', 'ST', 'S*ST', 'SST']
    name_upper = stock_name.upper().strip()
    
    # 按照长度从长到短排序，避免短前缀匹配到长前缀的一部分
    # 例如：'*ST'应该在'ST'之前检查
    sorted_prefixes = sorted(st_prefixes, key=len, reverse=True)
    
    for prefix in sorted_prefixes:
        if name_upper.startswith(prefix):
            # 进一步验证：确保前缀后面是空格或直接是股票名称
            # 避免误判如'STAR'这样的正常股票名称
            if len(name_upper) == len(prefix) or name_upper[len(prefix)] in [' ', '\t']:
                return True
            # 如果前缀后面紧跟字母，也认为是ST股票（如'ST华映'）
            elif len(name_upper) > len(prefix) and name_upper[len(prefix)].isalpha():
                return True
    
    return False

def calculate_limit_up_price(prev_close: float, limit_rate: float) -> float:
    """计算涨停价格（基于前收盘价和涨停幅度，四舍五入到0.01元）"""
    theoretical_price = prev_close * (1 + limit_rate / 100)
    # 四舍五入到0.01元（保留两位小数）
    return round(theoretical_price, 2)

def filter_limit_up_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """过滤真正的涨停股票（基于前收盘价计算理论涨停价）"""
    if df is None or df.empty:
        return df
    
    logger.info(f"开始过滤涨停股票，原始数据: {len(df)} 条")
    
    # 创建副本避免修改原数据
    filtered_df = df.copy()
    
    # 1. 过滤掉涨跌幅为负数的股票
    if '涨跌幅' in filtered_df.columns:
        before_count = len(filtered_df)
        filtered_df = filtered_df[filtered_df['涨跌幅'] > 0]
        negative_filtered = before_count - len(filtered_df)
        if negative_filtered > 0:
            logger.info(f"过滤掉涨跌幅为负数的股票: {negative_filtered} 只")
    
    # 检查必要字段
    required_fields = ['代码', '名称', '最新价']
    missing_fields = [field for field in required_fields if field not in filtered_df.columns]
    if missing_fields:
        logger.error(f"缺少必要字段: {missing_fields}")
        return pd.DataFrame()
    
    # 尝试获取前收盘价字段
    prev_close_field = None
    possible_prev_close_fields = ['昨收', '前收盘', '昨日收盘价', 'prev_close', '收盘价']
    for field in possible_prev_close_fields:
        if field in filtered_df.columns:
            prev_close_field = field
            break
    
    if prev_close_field is None:
        logger.warning("未找到前收盘价字段，尝试根据当前价格和涨跌幅反推")
        # 如果没有前收盘价，根据当前价格和涨跌幅反推
        if '最新价' in filtered_df.columns and '涨跌幅' in filtered_df.columns:
            filtered_df['昨收'] = filtered_df['最新价'] / (1 + filtered_df['涨跌幅'] / 100)
            prev_close_field = '昨收'
        else:
            logger.error("无法获取或计算前收盘价，无法进行精确涨停判断")
            return pd.DataFrame()
    
    logger.info(f"使用字段 '{prev_close_field}' 作为前收盘价")
    
    # 2. 根据前收盘价计算理论涨停价进行精确过滤
    valid_limit_up_stocks = []
    
    for idx, row in filtered_df.iterrows():
        stock_code = str(row.get('代码', '')).strip()
        stock_name = str(row.get('名称', '')).strip()
        current_price = float(row.get('最新价', 0))
        prev_close = float(row.get(prev_close_field, 0))
        change_pct = float(row.get('涨跌幅', 0))
        
        if prev_close <= 0:
            logger.debug(f"✗ {stock_code} {stock_name}: 前收盘价无效 ({prev_close})")
            continue
        
        # 获取股票市场信息
        market_info = get_stock_market_info(stock_code)
        
        # 判断是否为ST股票
        is_st = is_st_stock(stock_name)
        
        # 确定涨停幅度限制
        if is_st:
            limit_rate = 5.0  # ST股票涨停幅度为5%
            description = f"{market_info['description']} ST股票"
        else:
            limit_rate = market_info['limit_rate']
            description = market_info['description']
        
        # 计算理论涨停价（四舍五入到0.01元）
        theoretical_limit_price = calculate_limit_up_price(prev_close, limit_rate)
        
        # 计算实际涨幅
        actual_change_pct = (current_price - prev_close) / prev_close * 100
        
        # 判断是否为涨停：当前价格应该等于或非常接近理论涨停价
        price_tolerance = 0.01  # 价格容差：±0.01元
        pct_tolerance = 0.15    # 涨幅容差：±0.15%
        
        is_limit_up = (
            abs(current_price - theoretical_limit_price) <= price_tolerance or
            abs(actual_change_pct - limit_rate) <= pct_tolerance
        )
        
        if is_limit_up:
            # 添加市场信息到行数据
            row_dict = row.to_dict()
            row_dict['市场'] = market_info['market']
            row_dict['板块'] = market_info['board']
            row_dict['理论涨停幅度'] = limit_rate
            row_dict['理论涨停价'] = theoretical_limit_price
            row_dict['实际涨幅'] = actual_change_pct
            row_dict['是否ST'] = is_st
            row_dict['市场描述'] = description
            row_dict['前收盘价'] = prev_close
            valid_limit_up_stocks.append(row_dict)
            
            logger.debug(f"✓ {stock_code} {stock_name}: 当前价{current_price}元, 理论涨停价{theoretical_limit_price}元, 实际涨幅{actual_change_pct:.2f}% - {description}")
        else:
            logger.debug(f"✗ {stock_code} {stock_name}: 当前价{current_price}元, 理论涨停价{theoretical_limit_price}元, 实际涨幅{actual_change_pct:.2f}% - 不符合涨停标准")
    
    # 转换为DataFrame
    if valid_limit_up_stocks:
        result_df = pd.DataFrame(valid_limit_up_stocks)
        logger.info(f"✓ 过滤完成，真正的涨停股票: {len(result_df)} 只")
        
        # 按市场分类统计
        if '市场' in result_df.columns:
            market_stats = result_df['市场'].value_counts()
            logger.info(f"市场分布: {dict(market_stats)}")
        
        # 按板块分类统计
        if '板块' in result_df.columns:
            board_stats = result_df['板块'].value_counts()
            logger.info(f"板块分布: {dict(board_stats)}")
        
        # ST股票统计
        if '是否ST' in result_df.columns:
            st_count = result_df['是否ST'].sum()
            logger.info(f"ST股票数量: {st_count} 只")
        
        # 涨幅分布统计
        if '实际涨幅' in result_df.columns:
            avg_change = result_df['实际涨幅'].mean()
            min_change = result_df['实际涨幅'].min()
            max_change = result_df['实际涨幅'].max()
            logger.info(f"涨幅分布: 平均{avg_change:.2f}%, 最小{min_change:.2f}%, 最大{max_change:.2f}%")
        
        # 确保涨跌幅列格式化为2位小数
        if '涨跌幅' in result_df.columns:
            result_df['涨跌幅'] = result_df['涨跌幅'].round(2)
        if '实际涨幅' in result_df.columns:
            result_df['实际涨幅'] = result_df['实际涨幅'].round(2)
        
        # 按涨跌幅从高到低排序
        if '涨跌幅' in result_df.columns:
            result_df = result_df.sort_values('涨跌幅', ascending=False).reset_index(drop=True)
            logger.info(f"✓ 数据已按涨跌幅从高到低排序")
        
        return result_df
    else:
        logger.warning("⚠️ 没有找到符合涨停标准的股票")
        return pd.DataFrame()

def validate_data_quality(df: pd.DataFrame, source_name: str) -> Tuple[bool, List[str]]:
    """验证数据质量"""
    warnings = []
    is_valid = True
    
    # 检查数据数量
    if len(df) < MIN_EXPECTED_LIMIT_UP_COUNT:
        warnings.append(f"涨停股票数量异常少: {len(df)} < {MIN_EXPECTED_LIMIT_UP_COUNT}")
        if len(df) < 3:  # 如果少于3只，认为数据质量不合格
            is_valid = False
    
    # 检查必要字段
    required_fields = ['代码', '名称', '涨跌幅']
    missing_fields = [field for field in required_fields if field not in df.columns]
    if missing_fields:
        warnings.append(f"缺少必要字段: {missing_fields}")
        is_valid = False
    
    # 检查是否有涨跌幅为负数的股票（这不应该出现在涨停数据中）
    if '涨跌幅' in df.columns:
        negative_count = (df['涨跌幅'] < 0).sum()
        if negative_count > 0:
            warnings.append(f"发现涨跌幅为负数的股票: {negative_count} 只（将被过滤）")
        
        # 检查涨跌幅范围是否合理
        min_change = df['涨跌幅'].min()
        max_change = df['涨跌幅'].max()
        if min_change < -10 or max_change > 35:
            warnings.append(f"涨跌幅范围异常: {min_change:.2f}% ~ {max_change:.2f}%")
    
    # 检查是否有重复数据
    if '代码' in df.columns:
        duplicate_count = df['代码'].duplicated().sum()
        if duplicate_count > 0:
            warnings.append(f"发现重复股票代码: {duplicate_count} 条")
    
    if warnings:
        logger.warning(f"{source_name} 数据质量警告: {'; '.join(warnings)}")
    
    return is_valid, warnings

def get_multi_source_limit_up_data(target_date: str) -> Tuple[Optional[pd.DataFrame], Dict]:
    """使用多数据源获取涨停数据"""
    # 转换日期格式为YYYYMMDD
    date_obj = datetime.strptime(target_date, '%Y-%m-%d')
    date_str = date_obj.strftime('%Y%m%d')
    weekday_name = date_obj.strftime('%A')
    
    logger.info(f"开始多数据源获取 {target_date} ({weekday_name}) 的涨停数据")
    
    # 按质量评分排序数据源
    sorted_sources = sorted(DATA_SOURCES, key=lambda x: x.get_quality_score(), reverse=True)
    
    best_data = None
    best_source = None
    all_results = []
    
    for source in sorted_sources:
        logger.info(f"\n--- 尝试数据源 {source.name} (质量评分: {source.get_quality_score():.1f}) ---")
        
        # 尝试获取数据
        df, status = try_data_source(source, date_str)
        
        result_info = {
            'source': source.name,
            'function': source.function_name,
            'status': status,
            'data_count': len(df) if df is not None else 0,
            'success': df is not None and not df.empty,
            'quality_score': source.get_quality_score(),
            'warnings': []
        }
        
        if df is not None and not df.empty:
            # 数据质量验证
            is_valid, warnings = validate_data_quality(df, source.name)
            result_info['is_valid'] = is_valid
            result_info['warnings'] = warnings
            
            # 过滤真正的涨停股票
            filtered_df = filter_limit_up_stocks(df)
            result_info['filtered_count'] = len(filtered_df) if filtered_df is not None else 0
            
            # 如果这是第一个有效数据，或者质量更好，则使用它
            if best_data is None or (is_valid and len(filtered_df) > len(best_data)):
                best_data = filtered_df.copy() if filtered_df is not None and not filtered_df.empty else None
                best_source = source
                logger.info(f"✓ 选择 {source.name} 作为最佳数据源（过滤后: {len(filtered_df) if filtered_df is not None else 0} 只涨停股票）")
        
        all_results.append(result_info)
        
        # 添加延迟避免请求过快
        time.sleep(1)
    
    # 汇总信息
    summary = {
        'target_date': target_date,
        'best_source': best_source.name if best_source else None,
        'best_data_count': len(best_data) if best_data is not None else 0,
        'total_sources_tried': len(sorted_sources),
        'successful_sources': len([r for r in all_results if r['success']]),
        'all_results': all_results
    }
    
    if best_data is not None:
        logger.info(f"\n🎯 最终选择: {best_source.name}，获取 {len(best_data)} 只涨停股票")
        
        # 数据质量最终检查
        if len(best_data) < MIN_EXPECTED_LIMIT_UP_COUNT:
            logger.warning(f"⚠ 注意：涨停股票数量 ({len(best_data)}) 少于预期 ({MIN_EXPECTED_LIMIT_UP_COUNT})")
            logger.warning(f"可能原因：1) 该日期确实涨停股票较少 2) 非交易日 3) 数据源质量问题")
    else:
        logger.error(f"❌ 所有数据源都无法获取到有效数据")
        logger.error(f"尝试的数据源: {[s.name for s in sorted_sources]}")
    
    return best_data, summary

def ensure_directories():
    """确保必要的目录存在"""
    directories = [STOCK_DATA_PATH, LIMIT_UP_PATH, PLATE_PATH, INDUSTRY_PLATE_PATH, CONCEPT_PLATE_PATH]
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            logger.info(f"创建目录: {directory}")

def create_daily_summary(limit_up_df: Optional[pd.DataFrame], target_date: str, data_summary: Dict, date_explanation: str):
    """创建每日涨停汇总文件"""
    try:
        # 确保目录存在
        ensure_directories()
        
        # 生成汇总文件名
        summary_filename = f"{target_date}_涨停汇总.md"
        summary_path = os.path.join(LIMIT_UP_PATH, summary_filename)
        
        # 构建汇总内容
        content = f"# {target_date} 涨停股票汇总\n\n"
        content += f"## 📅 日期信息\n\n"
        content += f"- **查询日期**: {target_date}\n"
        content += f"- **日期说明**: {date_explanation}\n"
        content += f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        if limit_up_df is not None and not limit_up_df.empty:
            content += f"## 📊 数据概览\n\n"
            content += f"- **涨停股票数量**: {len(limit_up_df)} 只\n"
            content += f"- **数据来源**: {data_summary.get('best_source', '未知')}\n"
            content += f"- **数据质量**: {'优秀' if len(limit_up_df) >= MIN_EXPECTED_LIMIT_UP_COUNT else '一般'}\n\n"
            
            # 市场分布统计
            if '市场' in limit_up_df.columns:
                content += f"## 📊 市场分布\n\n"
                market_stats = limit_up_df['市场'].value_counts()
                for market, count in market_stats.items():
                    market_name = {'SSE': '上交所', 'SZSE': '深交所', 'BSE': '北交所', 'UNKNOWN': '未知'}.get(market, market)
                    content += f"- **{market_name}**: {count} 只\n"
                content += "\n"
                
                # 板块分布统计
                if '板块' in limit_up_df.columns:
                    content += f"## 🏢 板块分布\n\n"
                    board_stats = limit_up_df['板块'].value_counts()
                    for board, count in board_stats.items():
                        board_name = {'MAIN': '主板', 'GEM': '创业板', 'STAR': '科创板', 'UNKNOWN': '未知'}.get(board, board)
                        content += f"- **{board_name}**: {count} 只\n"
                    content += "\n"
                
                # ST股票统计
                if '是否ST' in limit_up_df.columns:
                    st_count = limit_up_df['是否ST'].sum()
                    normal_count = len(limit_up_df) - st_count
                    content += f"## 🚨 ST股票统计\n\n"
                    content += f"- **正常股票**: {normal_count} 只\n"
                    content += f"- **ST股票**: {st_count} 只\n\n"
            
            # 按涨跌幅从高到低排序
            if '涨跌幅' in limit_up_df.columns:
                limit_up_df_sorted = limit_up_df.sort_values('涨跌幅', ascending=False).reset_index(drop=True)
            else:
                limit_up_df_sorted = limit_up_df.reset_index(drop=True)
            
            # 涨停股票列表
            content += f"## 📈 涨停股票列表\n\n"
            content += "| 序号 | 股票代码 | 股票名称 | 最新价 | 涨跌幅 | 理论涨停 | 市场描述 | 成交额 | 流通市值 |\n"
            content += "|------|----------|----------|--------|--------|----------|----------|--------|----------|\n"
            
            for idx, row in limit_up_df_sorted.iterrows():
                # 格式化涨跌幅为保留2位小数
                change_pct = row.get('涨跌幅', 0)
                if isinstance(change_pct, (int, float)):
                    change_pct_str = f"{change_pct:.2f}%"
                else:
                    change_pct_str = f"{change_pct}%"
                
                # 格式化理论涨停幅度
                limit_rate = row.get('理论涨停幅度', 0)
                if isinstance(limit_rate, (int, float)):
                    limit_rate_str = f"{limit_rate:.2f}%"
                else:
                    limit_rate_str = f"{limit_rate}%"
                
                content += f"| {idx + 1} | {row.get('代码', '')} | {row.get('名称', '')} | "
                content += f"{row.get('最新价', '')} | {change_pct_str} | "
                content += f"{limit_rate_str} | {row.get('市场描述', '')} | "
                content += f"{row.get('成交额', '')} | {row.get('流通市值', '')} |\n"
        else:
            content += f"## ⚠️ 数据状态\n\n"
            content += f"- **状态**: 无涨停数据\n"
            content += f"- **可能原因**: 非交易日、该日期确实无涨停股票或数据源问题\n"
            content += f"- **尝试的数据源数量**: {data_summary.get('total_sources_tried', 0)}\n"
            content += f"- **成功的数据源数量**: {data_summary.get('successful_sources', 0)}\n\n"
        
        # 数据源信息
        content += f"## 🔍 数据源详情\n\n"
        if 'all_results' in data_summary:
            for result in data_summary['all_results']:
                status_icon = "✓" if result['success'] else "✗"
                content += f"- {status_icon} **{result['source']}**: {result['status']}\n"
        
        content += f"\n---\n\n"
        content += f"*本汇总由智能涨停数据获取脚本自动生成*\n"
        
        # 写入文件
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"✓ 汇总文件已保存: {summary_path}")
        
    except Exception as e:
        logger.error(f"创建汇总文件失败: {e}")

def main():
    """主函数"""
    try:
        # 解析命令行参数
        parser = argparse.ArgumentParser(description='A股涨停板数据智能获取脚本')
        parser.add_argument('--date', type=str, help='指定日期，格式：YYYY-MM-DD')
        parser.add_argument('--json', action='store_true', help='输出JSON格式数据')
        args = parser.parse_args()
        
        # 智能获取交易日期
        target_date, date_explanation = get_smart_trading_date(args.date)
        target_date_str = target_date.strftime('%Y-%m-%d')
        
        logger.info(f"🎯 {date_explanation}")
        logger.info(f"开始获取 {target_date_str} 的涨停数据（智能交易日模式）")
        
        # 确保目录存在
        ensure_directories()
        
        # 使用多数据源获取涨停数据
        limit_up_df, data_summary = get_multi_source_limit_up_data(target_date_str)
        
        if args.json:
            # JSON输出模式
            if limit_up_df is not None and not limit_up_df.empty:
                # 转换DataFrame为JSON格式
                stocks_data = []
                for _, row in limit_up_df.iterrows():
                    stock_info = {
                        "code": row.get('代码', ''),
                        "name": row.get('名称', ''),
                        "price": float(row.get('最新价', 0)) if pd.notna(row.get('最新价')) else 0,
                        "change": float(row.get('涨跌幅', 0)) if pd.notna(row.get('涨跌幅')) else 0,
                        "changePercent": float(row.get('涨跌幅', 0)) if pd.notna(row.get('涨跌幅')) else 0,
                        "volume": int(row.get('成交量', 0)) if pd.notna(row.get('成交量')) else 0,
                        "turnover": float(row.get('成交额', 0)) if pd.notna(row.get('成交额')) else 0,
                        "market": row.get('市场', 'UNKNOWN'),
                        "board": row.get('板块', 'UNKNOWN'),
                        "is_st": bool(row.get('是否ST', False))
                    }
                    stocks_data.append(stock_info)
                
                result = {
                    "success": True,
                    "date": target_date_str,
                    "count": len(limit_up_df),
                    "source": data_summary.get('best_source', '未知'),
                    "quality": "优秀" if len(limit_up_df) >= MIN_EXPECTED_LIMIT_UP_COUNT else "一般",
                    "stocks": stocks_data
                }
            else:
                result = {
                    "success": False,
                    "date": target_date_str,
                    "count": 0,
                    "source": data_summary.get('attempted_sources', []),
                    "quality": "无数据",
                    "stocks": [],
                    "message": f"{target_date_str} 无涨停数据"
                }
            
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            # 原有的日志输出模式
            if limit_up_df is not None and not limit_up_df.empty:
                # 创建每日汇总
                create_daily_summary(limit_up_df, target_date_str, data_summary, date_explanation)
                
                logger.info(f"✅ 成功完成 {target_date_str} 涨停数据获取和汇总")
                logger.info(f"📊 共获取 {len(limit_up_df)} 只涨停股票的数据")
                logger.info(f"🔍 数据来源: {data_summary.get('best_source')}")
                logger.info(f"📝 汇总文件已保存到Obsidian目录")
                
                # 质量评估
                if len(limit_up_df) >= MIN_EXPECTED_LIMIT_UP_COUNT:
                    logger.info(f"✅ 数据质量评估: 优秀 (数量充足)")
                else:
                    logger.warning(f"⚠️ 数据质量评估: 一般 (数量较少，请注意验证)")
            else:
                logger.warning(f"⚠️ {target_date_str} 无涨停数据")
                
                # 即使没有数据也创建汇总文件
                create_daily_summary(None, target_date_str, data_summary, date_explanation)
                logger.info(f"📝 空数据汇总文件已保存到Obsidian目录")
        
    except Exception as e:
        logger.error(f"❌ 程序执行失败: {e}")
        raise

if __name__ == "__main__":
    main()
