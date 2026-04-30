#!/usr/bin/env bash
# ===========================================================================
# b_up_creator_install.sh — B站 UP 主双技能一键安装
# 在 ~/.agents/skills/ 和各 IDE 目录下创建软链接，指向仓库中的
# bilibili-up-info 和 ai-creator-info 两个技能。
# 后续只需 git pull 仓库，所有技能自动更新。
#
# 安装方式：bash scripts/b_up_creator_install.sh
# ===========================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
GLOBAL_SKILLS="$HOME/.agents/skills"

# ── 只处理 B 站 UP 主相关技能 ──────────────────────────────
SKILL_SRC=(
  "B站/bilibili-up-info"
  "B站/ai-creator-info"
)

# ── 颜色输出 ──────────────────────────────────────────────
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  B站 UP 主双技能安装脚本${NC}"
echo -e "${BLUE}  仓库路径: $REPO_DIR${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ── 1. 安装到 ~/.agents/skills/ ──────────────────────────
echo -e "${YELLOW}[1/2] 安装到全局目录 ~/.agents/skills/ ...${NC}"
mkdir -p "$GLOBAL_SKILLS"

for src_rel in "${SKILL_SRC[@]}"; do
  link_name="${src_rel##*/}"
  target="$REPO_DIR/$src_rel"
  link_path="$GLOBAL_SKILLS/$link_name"

  if [ ! -d "$target" ]; then
    echo -e "  ${YELLOW}⚠ 跳过：$target 不存在${NC}"
    continue
  fi

  # 删除已存在的目录或链接
  if [ -L "$link_path" ] || [ -d "$link_path" ]; then
    rm -rf "$link_path"
  fi

  ln -s "$target" "$link_path"
  echo -e "  ${GREEN}✓${NC} $link_name → $target"
done

echo ""

# ── 2. 同步到各 IDE 目录 ────────────────────────────────
echo -e "${YELLOW}[2/2] 同步到 IDE 目录 ...${NC}"
installed_count=0

for ide_dir in \
  "$HOME/.codebuddy/skills" \
  "$HOME/.cursor/skills" \
  "$HOME/.claude/skills" \
  "$HOME/.trae/skills" \
  "$HOME/.cline/skills" \
  "$HOME/.windsurf/skills" \
  "$HOME/.codex/skills" \
  "$HOME/.hermes/skills"
do
  if [ -d "$(dirname "$ide_dir")" ]; then
    mkdir -p "$ide_dir"
    for src_rel in "${SKILL_SRC[@]}"; do
      link_name="${src_rel##*/}"
      global_link="$GLOBAL_SKILLS/$link_name"
      ide_link="$ide_dir/$link_name"

      if [ -L "$ide_link" ] || [ -d "$ide_link" ]; then
        rm -rf "$ide_link"
      fi

      if [ -L "$global_link" ] || [ -d "$global_link" ]; then
        ln -s "$global_link" "$ide_link"
      fi
    done
    echo -e "  ${GREEN}✓${NC} $ide_dir"
    installed_count=$((installed_count + 1))
  fi
done

if [ "$installed_count" -eq 0 ]; then
  echo -e "  ${YELLOW}(未发现其他 IDE 目录)${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  安装完成！${NC}"
echo -e "${GREEN}  两个 B 站技能已就绪${NC}"
echo -e "${GREEN}  下次 git pull 后，全局同步更新${NC}"
echo -e "${GREEN}========================================${NC}"
