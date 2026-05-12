#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全市场股票获取器 - 启动脚本

使用方法：
1. 获取所有股票：python run_stocks_fetcher.py
2. 只获取指定交易所：python run_stocks_fetcher.py --exchange SSE
3. 禁用增量更新：python run_stocks_fetcher.py --no-update
4. 查看统计信息：python run_stocks_fetcher.py --stats
"""

import argparse
import sys
import os
from datetime import datetime
from all_stocks_fetcher import AllStocksFetcher

def print_banner():
    """打印系统横幅"""
    print("=" * 70)
    print("🚀 全市场股票信息获取器 v1.2")
    print("=" * 70)
    print("功能特点：")
    print("✓ 按交易所分类获取：上交所、深交所、北交所")
    print("✓ 包含股票代码、股票名称、上市日期")
    print("✓ 支持增量更新，检测新上市和退市股票")
    print("✓ 按上市日期倒序排序")
    print("✓ 东方财富异常时自动切换 AkShare 重建")
    print("✓ 额外输出 已上市新股 / 待上市新股 两份精确 IPO 视图")
    print("✓ 使用巨潮/新股源补齐同花顺已展示的待上市与近期新股")
    print("✓ 支持注入同花顺 Cookie，会话可用时优先按真页校验")
    print("✓ 使用 Scrapling 校验同花顺网页样本")
    print("=" * 70)
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

def show_statistics():
    """显示股票统计信息"""
    print("📊 股票统计信息查询...")
    
    try:
        fetcher = AllStocksFetcher()
        stats = fetcher.get_summary_statistics()
        
        print("\n📈 当前股票数据统计:")
        print("=" * 50)
        
        for exchange, stat in stats.items():
            if exchange != 'total':
                print(f"{stat['name']}: {stat['count']} 只股票")
                print(f"  文件: {stat['file']}")
                
                # 获取文件修改时间
                file_path = os.path.join(fetcher.output_dir, stat['file'])
                if os.path.exists(file_path):
                    mtime = os.path.getmtime(file_path)
                    last_update = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                    print(f"  最后更新: {last_update}")
                print()
                
        print(f"📊 总计: {stats['total']} 只A股股票")
        
        # 显示文件位置
        output_dir = os.path.abspath(fetcher.output_dir)
        print(f"\n💾 数据文件位置: {output_dir}")
        
        # 列出所有CSV文件
        csv_files = [f for f in os.listdir(fetcher.output_dir) if f.endswith('.csv')]
        if csv_files:
            print("\n📁 生成的CSV文件:")
            for file in csv_files:
                file_path = os.path.join(fetcher.output_dir, file)
                if os.path.exists(file_path):
                    size = os.path.getsize(file_path) / 1024  # KB
                    print(f"  {file} ({size:.1f} KB)")
                    
    except Exception as e:
        print(f"❌ 获取统计信息失败: {e}")
        return False
        
    return True

def fetch_single_exchange(exchange_code):
    """获取单个交易所的股票信息"""
    exchange_names = {
        'SSE': '上海证券交易所',
        'SZSE': '深圳证券交易所', 
        'BSE': '北京证券交易所'
    }
    
    if exchange_code not in exchange_names:
        print(f"❌ 不支持的交易所代码: {exchange_code}")
        print("支持的交易所代码: SSE, SZSE, BSE")
        return False
        
    print(f"🔍 开始获取 {exchange_names[exchange_code]} 股票信息...")
    
    try:
        fetcher = AllStocksFetcher()
        success = fetcher.fetch_exchange_stocks(exchange_code, enable_update=True)
        
        if success:
            print(f"\n✅ {exchange_names[exchange_code]} 股票信息获取成功！")
            
            # 显示结果统计
            stats = fetcher.get_summary_statistics()
            if exchange_code in stats:
                stat = stats[exchange_code]
                print(f"📊 获取了 {stat['count']} 只股票")
                print(f"💾 保存到: {stat['file']}")
        else:
            print(f"❌ {exchange_names[exchange_code]} 股票信息获取失败")
            
        return success
        
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        return False

def fetch_all_exchanges(enable_update=True):
    """获取所有交易所的股票信息"""
    print("🔍 开始获取全市场股票信息...")
    
    try:
        fetcher = AllStocksFetcher()
        results = fetcher.fetch_all_stocks(enable_update=enable_update)
        
        # 统计成功和失败的交易所
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        if success_count == total_count:
            print("\n🎉 所有交易所股票信息获取成功！")
        elif success_count > 0:
            print(f"\n⚠️  部分成功：{success_count}/{total_count} 个交易所获取成功")
        else:
            print("\n❌ 所有交易所股票信息获取失败")
            return False
            
        # 显示详细统计
        stats = fetcher.get_summary_statistics()
        print("\n📊 获取结果统计:")
        print("=" * 50)
        
        for exchange, stat in stats.items():
            if exchange != 'total':
                status = "✅" if results.get(exchange, False) else "❌"
                print(f"{status} {stat['name']}: {stat['count']} 只股票")
                
        print(f"\n📈 总计: {stats['total']} 只A股股票")
        print(f"💾 数据保存位置: {os.path.abspath(fetcher.output_dir)}")
        
        return success_count > 0
        
    except Exception as e:
        print(f"❌ 系统错误: {e}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='全市场股票信息获取器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python run_stocks_fetcher.py                    # 获取所有交易所股票
  python run_stocks_fetcher.py --exchange SSE     # 只获取上交所股票
  python run_stocks_fetcher.py --stats            # 查看统计信息
  python run_stocks_fetcher.py --no-update        # 禁用增量更新
        """
    )
    
    parser.add_argument(
        '--exchange',
        choices=['SSE', 'SZSE', 'BSE'],
        help='指定获取的交易所 (SSE=上交所, SZSE=深交所, BSE=北交所)'
    )
    
    parser.add_argument(
        '--no-update',
        action='store_true',
        help='禁用增量更新检测'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='显示股票统计信息'
    )
    
    parser.add_argument(
        '--test-api',
        action='store_true',
        help='测试API访问状态'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='静默模式，减少输出信息'
    )
    
    args = parser.parse_args()
    
    # 静默模式下不显示横幅
    if not args.quiet:
        print_banner()
    
    success = True
    
    try:
        if args.test_api:
            # 测试API访问状态
            print("\n🔍 测试API访问状态...")
            fetcher = AllStocksFetcher()
            test_results = fetcher.test_api_access()
            
            print("\n📊 API测试结果:")
            for api_name, status in test_results.items():
                status_icon = "✅" if status else "❌"
                api_display = {
                    'sina': '新浪财经',
                    'tencent': '腾讯财经', 
                    'eastmoney': '东方财富'
                }
                print(f"  {status_icon} {api_display[api_name]}: {'正常' if status else '异常'}")
                
            working_apis = sum(test_results.values())
            print(f"\n📈 可用API数量: {working_apis}/3")
            
            if working_apis == 0:
                print("\n⚠️  所有API都无法访问，请检查网络连接或稍后重试")
            elif working_apis < 3:
                print("\n⚠️  部分API无法访问，系统将使用可用的API继续工作")
            else:
                print("\n✅ 所有API访问正常")
            success = working_apis > 0
            
        elif args.stats:
            # 显示统计信息
            success = show_statistics()
            
        elif args.exchange:
            # 获取指定交易所
            success = fetch_single_exchange(args.exchange)
            
        else:
            # 获取所有交易所
            enable_update = not args.no_update
            success = fetch_all_exchanges(enable_update)
            
    except KeyboardInterrupt:
        print("\n⚠️  用户中断操作")
        success = False
    except Exception as e:
        print(f"\n❌ 程序异常: {e}")
        success = False
        
    # 退出码
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
