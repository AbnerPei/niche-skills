#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import urllib.request
import os

SKILL_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SKILLS_ROOT = os.path.abspath(os.path.join(SKILL_ROOT, ".."))
STOCKMASTER_ROOT = os.environ.get("STOCKMASTER_ROOT", os.path.abspath(os.path.join(SKILLS_ROOT, "..", "StockMaster")))

url = "https://registry.npmmirror.com/china-division/latest/files/dist/pca.json"

def download_and_format_regions():
    print("正在下载全国省市区数据...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
    
    # 格式化数据，处理 "市辖区"、"县" 等特殊名称
    for province in data:
        if 'children' in province:
            for city in province['children']:
                if city['name'] in ['市辖区', '县']:
                    city['name'] = province['name'] # 用省名代替，如 北京市 -> 北京市 -> 东城区
                # 如果是直辖市县级市如"省直辖县级行政区划"，保留原样或用省名
                elif city['name'] == '省直辖县级行政区划':
                    city['name'] = '直辖县'
    
    # 保存到项目目录
    target_dir = os.path.join(STOCKMASTER_ROOT, 'StockMaster', 'Tools')
    target_path = os.path.join(target_dir, 'RegionData.json')
    
    with open(target_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
        
    print(f"成功保存全国省市区数据至: {target_path}")

if __name__ == '__main__':
    download_and_format_regions()
