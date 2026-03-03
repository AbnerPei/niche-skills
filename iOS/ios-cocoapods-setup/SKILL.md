---
name: ios-cocoapods-setup
description: This skill should be used when users need to set up CocoaPods for a new iOS project. It automates the creation and configuration of Podfile with specific dependencies and sources.
---

# iOS CocoaPods Setup Skill

## Overview

Automate the setup of CocoaPods for new iOS projects, including project validation, Podfile generation with custom sources and dependencies, and workspace opening.

## When to Use This Skill

Use this skill when:
- User has created a new iOS Xcode project and wants to add CocoaPods support
- User mentions setting up CocoaPods or `pod init`
- User needs to configure a Podfile with custom sources and dependencies
- User wants to initialize dependencies for a new iOS project

## Prerequisites

Before using this skill, ensure:
1. **CocoaPods is installed**: Verify with `pod --version`
2. **Xcode project exists**: User must have created an `.xcodeproj` file using Xcode
3. **Project directory is accessible**: Skill needs to navigate to the project directory

## Core Workflow

### Step 1: Validate Xcode Project

Check if an `.xcodeproj` file exists in the current directory.

**Validation Logic:**
```
IF .xcodeproj file exists:
    - Extract project name from .xcodeproj file
    - Continue to Step 2
ELSE:
    - Output error message: "请先用Xcode创建一个iOS项目工程,如:CurcorDemo.xcodeproj"
    - STOP workflow
```

**Detection Method:**
- List files in current directory
- Check for files ending with `.xcodeproj`
- Extract project name (e.g., `CurcorDemo.xcodeproj` → project name = `CurcorDemo`)

### Step 2: Navigate to Project Directory

Change to the project directory.

**Action:**
```bash
cd /path/to/project/directory
```

**Note**: If user provides a specific path (e.g., `/Users/hb39027/Documents/xx/CurcorDemo`), use that path. Otherwise, use the current working directory.

### Step 3: Initialize Podfile

Run `pod init` to generate the initial Podfile.

**Command:**
```bash
pod init
```

**Expected Output:**
- Creates `Podfile` in the project directory
- Podfile will have default structure with the project target

### Step 4: Configure Podfile

Replace the generated Podfile with the custom configuration.

**Important Notes:**
- Replace `CurcorDemo` with the actual project name extracted from Step 1
- Preserve the exact format and indentation
- Include all specified sources and dependencies

**Podfile Template:**
```ruby
source 'https://github.com/CocoaPods/Specs.git'
platform :ios, '15.6'

target 'CurcorDemo' do
  # Comment the next line if you don't want to use dynamic frameworks
  use_frameworks!

  # Pods for CurcorDemo
  pod 'Alamofire', '5.10.2'
  pod 'SnapKit', '5.7.1'
  pod 'Kingfisher'
  pod 'Then', '3.0.0'

end
```

**Replacement Logic:**
1. Read the generated `Podfile`
2. Replace entire content with the template
3. Replace all instances of `CurcorDemo` with actual project name:
   - In `target 'CurcorDemo' do`
   - In `# Pods for CurcorDemo`

**Dependencies Overview:**

| Pod | Version | Purpose |
|-----|---------|---------|
| Alamofire | 5.10.2 | HTTP networking library |
| SnapKit | 5.7.1 | Auto Layout DSL |
| Kingfisher | release_8.1.3 (git) | Image loading and caching |
| Then | 3.0.0 | Syntactic sugar for initialization |

### Step 5: Install Dependencies

Run `pod install` to download and install all dependencies.

**Command:**
```bash
pod install
```

**Expected Process:**
- Download dependencies from specified sources
- Resolve dependency tree
- Generate `Podfile.lock`
- Create `.xcworkspace` file
- Create `Pods` directory

**Expected Output:**
```
Analyzing dependencies
Downloading dependencies
Installing Alamofire (5.10.2)
Installing SnapKit (5.7.1)
Installing Then (3.0.0)
Installing Kingfisher (from git@...)
Generating Pods project
Integrating client project

[!] Please close any current Xcode sessions and use `CurcorDemo.xcworkspace` for this project from now on.
```

### Step 6: Open Workspace

Instruct user to open the `.xcworkspace` file.

**Command:**
```bash
open CurcorDemo.xcworkspace
```

**Important:**
- Replace `CurcorDemo` with actual project name
- Use `.xcworkspace`, NOT `.xcodeproj`
- All future development must use `.xcworkspace`

**User Instructions:**
```
✅ CocoaPods 设置完成!

请使用以下命令打开工程:
  open CurcorDemo.xcworkspace

⚠️ 注意:
  - 以后开发必须使用 .xcworkspace 文件,不要使用 .xcodeproj
  - .xcworkspace 包含了项目主工程和 Pods 项目
```

## Error Handling

### Common Errors and Solutions

#### Error 1: No .xcodeproj file found
```
Error: 请先用Xcode创建一个iOS项目工程,如:CurcorDemo.xcodeproj
```
**Solution:** Instruct user to create project in Xcode first

#### Error 2: CocoaPods not installed
```
Error: command not found: pod
```
**Solution:** Install CocoaPods:
```bash
sudo gem install cocoapods
```

#### Error 3: Git authentication failed
```
Error: fatal: could not read Username for 'ssh://git@gitlab.xx.cn...'
```
**Solution:**
- Ensure SSH keys are configured for GitLab
- Check network connectivity
- Verify GitLab access permissions

#### Error 4: Pod install fails due to version conflicts
```
Error: [!] Unable to find a specification for 'Alamofire'
```
**Solution:**
- Update CocoaPods repo: `pod repo update`
- Check network connectivity
- Verify source URLs are correct

#### Error 5: Permission denied writing to directory
```
Error: Permission denied @ dir_s_mkdir
```
**Solution:**
- Check directory permissions
- Ensure write access to project directory
- Try running with appropriate permissions

## Script Implementation

### Execution Flow

The skill can be implemented as a shell script with the following logic:

```bash
#!/bin/bash

# Step 1: Validate Xcode Project
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
    echo "❌ 错误: 请先用Xcode创建一个iOS项目工程,如:CurcorDemo.xcodeproj"
    exit 1
fi

echo "✅ 找到项目: $PROJECT_NAME"

# Step 2: Navigate to project directory
cd "$PROJECT_DIR"
echo "📍 当前目录: $(pwd)"

# Step 3: Initialize Podfile
echo "📝 执行 pod init..."
pod init

if [ $? -ne 0 ]; then
    echo "❌ pod init 失败"
    exit 1
fi

# Step 4: Configure Podfile
echo "⚙️  配置 Podfile..."

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
    echo "❌ 配置 Podfile 失败"
    exit 1
fi

echo "✅ Podfile 配置完成"

# Step 5: Install Dependencies
echo "📦 执行 pod install..."
pod install

if [ $? -ne 0 ]; then
    echo "❌ pod install 失败"
    exit 1
fi

# Step 6: Open Workspace
echo "🚀 打开工程..."
open "$PROJECT_NAME.xcworkspace"

echo ""
echo "✅ CocoaPods 设置完成!"
echo ""
echo "📋 项目信息:"
echo "  - 项目名: $PROJECT_NAME"
echo "  - Podfile: $PROJECT_DIR/Podfile"
echo "  - Workspace: $PROJECT_DIR/$PROJECT_NAME.xcworkspace"
echo ""
echo "⚠️  注意:"
echo "  - 以后开发必须使用 .xcworkspace 文件,不要使用 .xcodeproj"
echo "  - .xcworkspace 包含了项目主工程和 Pods 项目"
echo ""
```

## Output Format

### Success Output

```markdown
✅ CocoaPods 设置完成!

📋 项目信息:
  - 项目名: CurcorDemo
  - Podfile: /path/to/CurcorDemo/Podfile
  - Workspace: /path/to/CurcorDemo/CurcorDemo.xcworkspace

📦 已安装的依赖:
  - Alamofire (5.10.2)
  - SnapKit (5.7.1)
  - Kingfisher (from git@...)
  - Then (3.0.0)

⚠️  注意:
  - 以后开发必须使用 .xcworkspace 文件,不要使用 .xcodeproj
  - .xcworkspace 包含了项目主工程和 Pods 项目

🚀 下一步:
  使用以下命令打开工程:
  open CurcorDemo.xcworkspace
```

### Error Output

```markdown
❌ 错误: 请先用Xcode创建一个iOS项目工程,如:CurcorDemo.xcodeproj

💡 解决步骤:
  1. 打开 Xcode
  2. 选择 File > New > Project
  3. 选择 iOS > App
  4. 填写项目信息并保存
  5. 重新运行此 skill
```

## Troubleshooting

### Issue: pod install is very slow

**Solution:**
```bash
# 清理缓存
pod cache clean --all

# 更新 repo
pod repo update

# 重新安装
pod install
```

### Issue: Dependency version conflicts

**Solution:**
- Check `Podfile.lock` for resolved versions
- Adjust versions in Podfile if needed
- Run `pod update [pod_name]` for specific dependency

### Issue: SSH connection to GitLab fails

**Solution:**
```bash
# Test SSH connection
ssh -T git@gitlab.xx.cn -p 10022

# Check SSH keys
ls -la ~/.ssh

# Add SSH key to GitLab account
```

## Additional Resources

### Documentation
- [CocoaPods Official Guide](https://guides.cocoapods.org/)
- [CocoaPods Getting Started](https://guides.cocoapods.org/using/getting-started.html)
- [Podfile Syntax](https://guides.cocoapods.org/syntax/podfile.html)

### Common Commands
```bash
pod --version              # Check version
pod init                   # Initialize Podfile
pod install                # Install dependencies
pod update                 # Update dependencies
pod outdated               # Check for updates
pod cache clean --all      # Clear cache
pod deintegrate            # Remove CocoaPods from project
```

## Best Practices

1. **Commit Podfile and Podfile.lock** to version control
2. **Commit .xcworkspace** but **ignore .xcodeproj** (or keep both for reference)
3. **Ignore Pods directory** in version control (add to .gitignore)
4. **Use .xcworkspace** for all future development
5. **Update dependencies carefully** - test after each update
6. **Keep Podfile.lock** to ensure consistent builds across team members

## Customization

### Adding More Dependencies

To add more pods to the template, simply add them to the Podfile content:

```ruby
pod 'YourPod', '1.0.0'
pod 'AnotherPod', :git => 'git@github.com:user/repo.git', :branch => 'main'
```

### Changing Platform Version

Modify the platform line in Podfile:

```ruby
platform :ios, '14.0'  # Change to your target iOS version
```

### Using Different Sources

You can add or remove sources at the top of Podfile:

```ruby
source 'https://github.com/CocoaPods/Specs.git'  # Official repo
source 'https://your-private-spec-repo.com'      # Private repo
```
