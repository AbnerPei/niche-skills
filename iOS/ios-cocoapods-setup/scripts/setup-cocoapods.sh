#!/bin/bash

# iOS CocoaPods Setup Script
# This script automates the setup of CocoaPods for iOS projects

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Validate Xcode Project
echo -e "${BLUE}🔍 Step 1: 验证 Xcode 项目...${NC}"

PROJECT_DIR=$(pwd)
PROJECT_NAME=""

# Find .xcodeproj file
for file in "$PROJECT_DIR"/*.xcodeproj; do
    if [ -d "$file" ]; then
        PROJECT_NAME=$(basename "$file" .xcodeproj)
        break
    fi
done

if [ -z "$PROJECT_NAME" ]; then
    echo -e "${RED}❌ 错误: 请先用Xcode创建一个iOS项目工程,如:CurcorDemo.xcodeproj${NC}"
    echo ""
    echo -e "${YELLOW}💡 解决步骤:${NC}"
    echo "  1. 打开 Xcode"
    echo "  2. 选择 File > New > Project"
    echo "  3. 选择 iOS > App"
    echo "  4. 填写项目信息并保存"
    echo "  5. 重新运行此脚本"
    exit 1
fi

echo -e "${GREEN}✅ 找到项目: $PROJECT_NAME${NC}"
echo ""

# Step 2: Navigate to project directory
echo -e "${BLUE}📍 Step 2: 切换到项目目录...${NC}"
cd "$PROJECT_DIR"
echo -e "${GREEN}✅ 当前目录: $(pwd)${NC}"
echo ""

# Step 3: Initialize Podfile
echo -e "${BLUE}📝 Step 3: 执行 pod init...${NC}"
if ! command -v pod &> /dev/null; then
    echo -e "${RED}❌ 错误: 未找到 CocoaPods,请先安装:${NC}"
    echo "  sudo gem install cocoapods"
    exit 1
fi

pod init
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ pod init 失败${NC}"
    exit 1
fi
echo -e "${GREEN}✅ pod init 完成${NC}"
echo ""

# Step 4: Configure Podfile
echo -e "${BLUE}⚙️  Step 4: 配置 Podfile...${NC}"

PODFILE_CONTENT="source 'https://github.com/CocoaPods/Specs.git'
platform :ios, '15.6'

target '$PROJECT_NAME' do
  # Comment the next line if you don't want to use dynamic frameworks
  use_frameworks!

  # Pods for $PROJECT_NAME
  pod 'Alamofire', '5.10.2'
  pod 'SnapKit', '5.7.1'
  pod 'Kingfisher'
  pod 'Then', '3.0.0'

end"

echo "$PODFILE_CONTENT" > Podfile

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ 配置 Podfile 失败${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Podfile 配置完成${NC}"
echo ""

# Step 5: Install Dependencies
echo -e "${BLUE}📦 Step 5: 执行 pod install...${NC}"
pod install

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ pod install 失败${NC}"
    exit 1
fi
echo -e "${GREEN}✅ pod install 完成${NC}"
echo ""

# Step 6: Open Workspace
echo -e "${BLUE}🚀 Step 6: 打开工程...${NC}"
open "$PROJECT_NAME.xcworkspace"
echo ""

# Success Message
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ CocoaPods 设置完成!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}📋 项目信息:${NC}"
echo -e "  - 项目名: ${YELLOW}$PROJECT_NAME${NC}"
echo -e "  - Podfile: ${YELLOW}$PROJECT_DIR/Podfile${NC}"
echo -e "  - Workspace: ${YELLOW}$PROJECT_DIR/$PROJECT_NAME.xcworkspace${NC}"
echo ""
echo -e "${BLUE}📦 已安装的依赖:${NC}"
echo -e "  - ${YELLOW}Alamofire${NC} (5.10.2) - HTTP 网络库"
echo -e "  - ${YELLOW}SnapKit${NC} (5.7.1) - Auto Layout DSL"
echo -e "  - ${YELLOW}Kingfisher${NC} (release_8.1.3 from git) - 图片加载缓存"
echo -e "  - ${YELLOW}Then${NC} (3.0.0) - 初始化语法糖"
echo ""
echo -e "${YELLOW}⚠️  注意事项:${NC}"
echo -e "  1. 以后开发必须使用 ${RED}.xcworkspace${NC} 文件,${RED}不要使用${NC} .xcodeproj"
echo -e "  2. .xcworkspace 包含了项目主工程和 Pods 项目"
echo -e "  3. 请将 Podfile 和 Podfile.lock 提交到版本控制"
echo -e "  4. 请在 .gitignore 中添加 Pods/ 目录"
echo ""
echo -e "${GREEN}🚀 下一步:${NC}"
echo -e "  使用以下命令打开工程:"
echo -e "  ${BLUE}open $PROJECT_NAME.xcworkspace${NC}"
echo ""
