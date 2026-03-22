#!/bin/bash
# Verantyx CLI — 統合起動スクリプト
# Usage: ./verantyx-start.sh [command]
#
# Commands:
#   setup     — 初回セットアップ（環境変数 + モデル設定）
#   start     — Gateway起動 + 状態表示
#   stop      — Gateway停止
#   chat      — エージェントと対話
#   status    — 現在の状態表示
#   memory    — 記憶一覧表示
#   inject    — 記憶注入プレビュー
#   vfs       — VFS一覧表示
#   (なし)    — Gateway起動 + 記憶表示 + 対話開始

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VERANTYX_PORT="${VERANTYX_PORT:-18790}"

# 色
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
GRAY='\033[0;90m'
NC='\033[0m'

banner() {
    echo ""
    echo -e "${CYAN}🧬 Verantyx CLI${NC} ${GRAY}v0.1.0${NC}"
    echo -e "${GRAY}   AI Memory Refresh System — Spatial Memory + Commander Pattern${NC}"
    echo ""
}

ensure_env() {
    # .env がなければ作成
    if [ ! -f .env ] || ! grep -q "VERANTYX_MEMORY_ROOT" .env 2>/dev/null; then
        echo -e "${YELLOW}Setting up .env...${NC}"
        cat >> .env << 'ENVEOF'
VERANTYX_MEMORY_ROOT=/Users/motonishikoudai/.claude/projects/-Users-motonishikoudai-verantyx-v6/memory
VERANTYX_VFS_MAPPING=/Users/motonishikoudai/verantyx_v6/.verantyx/vfs_mapping.json
ENVEOF
        echo -e "${GREEN}✅ .env configured${NC}"
    fi

    # ~/.verantyx/.env も確認
    mkdir -p ~/.verantyx
    if [ ! -f ~/.verantyx/.env ] || ! grep -q "VERANTYX_MEMORY_ROOT" ~/.verantyx/.env 2>/dev/null; then
        cat >> ~/.verantyx/.env << 'ENVEOF'
VERANTYX_MEMORY_ROOT=/Users/motonishikoudai/.claude/projects/-Users-motonishikoudai-verantyx-v6/memory
VERANTYX_VFS_MAPPING=/Users/motonishikoudai/verantyx_v6/.verantyx/vfs_mapping.json
ENVEOF
    fi
}

stop_existing_gateway() {
    # 既存のOpenClaw Gatewayを停止（ポート競合回避）
    if lsof -i :18789 >/dev/null 2>&1; then
        echo -e "${YELLOW}Stopping existing OpenClaw gateway on :18789...${NC}"
        node openclaw.mjs gateway stop 2>/dev/null || true
        sleep 1
    fi
    # Verantyxポートも確認
    if lsof -i :${VERANTYX_PORT} >/dev/null 2>&1; then
        echo -e "${YELLOW}Port ${VERANTYX_PORT} in use, stopping...${NC}"
        kill $(lsof -t -i :${VERANTYX_PORT}) 2>/dev/null || true
        sleep 1
    fi
}

start_gateway() {
    stop_existing_gateway
    echo -e "${GREEN}Starting Verantyx Gateway on port ${VERANTYX_PORT}...${NC}"
    VERANTYX_COMMANDER_MODE=true node openclaw.mjs gateway run --port ${VERANTYX_PORT} &
    GATEWAY_PID=$!
    sleep 3

    if kill -0 $GATEWAY_PID 2>/dev/null; then
        echo -e "${GREEN}✅ Gateway running (PID: $GATEWAY_PID)${NC}"
    else
        echo -e "${RED}❌ Gateway failed to start${NC}"
        return 1
    fi
}

auto_freshness_check() {
    echo -e "${CYAN}🔍 Auto Freshness Check${NC}"
    local output=$(node openclaw.mjs spatial freshness 2>&1 | grep -v "Config was" | grep -v "🦞")
    local stale_count=$(echo "$output" | grep -c "❌" || true)
    local warn_count=$(echo "$output" | grep -c "⚠️" || true)

    if [ "$stale_count" -gt 0 ]; then
        echo -e "${RED}   ❌ ${stale_count} stale memories detected!${NC}"
        echo "$output" | grep "❌"
        echo -e "${YELLOW}   → These memories may be outdated. Consider regenerating.${NC}"
    elif [ "$warn_count" -gt 0 ]; then
        echo -e "${YELLOW}   ⚠️  ${warn_count} memories may be outdated${NC}"
    else
        echo -e "${GREEN}   ✅ All memories are fresh${NC}"
    fi
    echo ""
}

show_status() {
    echo -e "${CYAN}📊 Status${NC}"
    echo ""

    # 記憶状態
    echo -e "${GREEN}  Memory:${NC}"
    node openclaw.mjs spatial list 2>&1 | grep -v "Config was" | grep -v "🦞" | grep -v "^$"
    echo ""

    # VFS状態
    echo -e "${GREEN}  VFS Files:${NC}"
    local count=$(node openclaw.mjs vfs list 2>&1 | grep -v "Config was" | grep -v "🦞" | grep "file_" | wc -l | tr -d ' ')
    echo -e "    ${count} virtual files registered"
    echo ""

    # Gateway状態
    if lsof -i :${VERANTYX_PORT} >/dev/null 2>&1; then
        echo -e "${GREEN}  Gateway: ✅ Running on :${VERANTYX_PORT}${NC}"
    else
        echo -e "${YELLOW}  Gateway: ⚠️  Not running${NC}"
    fi
    echo ""
}

cmd_setup() {
    banner
    echo -e "${CYAN}🔧 Initial Setup${NC}"
    echo ""

    ensure_env
    echo ""

    # APIキー確認
    if [ -z "$ANTHROPIC_API_KEY" ] && ! grep -q "ANTHROPIC_API_KEY" .env 2>/dev/null && ! grep -q "ANTHROPIC_API_KEY" ~/.verantyx/.env 2>/dev/null; then
        echo -e "${YELLOW}No ANTHROPIC_API_KEY found.${NC}"
        echo -e "${GRAY}Running model configuration...${NC}"
        echo ""
        node openclaw.mjs configure --section model
    else
        echo -e "${GREEN}✅ API key found${NC}"
    fi

    echo ""
    echo -e "${GREEN}✅ Setup complete!${NC}"
    echo -e "${GRAY}   Run: ./verantyx-start.sh start${NC}"
}

cmd_start() {
    banner
    ensure_env
    auto_freshness_check
    start_gateway
    echo ""
    show_status
}

cmd_stop() {
    echo -e "${YELLOW}Stopping Verantyx Gateway...${NC}"
    if lsof -i :${VERANTYX_PORT} >/dev/null 2>&1; then
        kill $(lsof -t -i :${VERANTYX_PORT}) 2>/dev/null || true
        echo -e "${GREEN}✅ Stopped${NC}"
    else
        echo -e "${GRAY}Gateway was not running${NC}"
    fi
}

cmd_chat() {
    ensure_env

    # Clear stale session locks (from previous crashes/force-kills)
    rm -f ~/.openclaw/agents/*/sessions/*.lock 2>/dev/null
    pkill -f "openclaw.mjs agent" 2>/dev/null || true

    if ! lsof -i :${VERANTYX_PORT} >/dev/null 2>&1; then
        echo -e "${YELLOW}Gateway not running. Starting...${NC}"
        start_gateway
        echo ""
    fi

    # Use vchat command for rich thinking/tool display
    VERANTYX_COMMANDER_MODE=true node openclaw.mjs vchat
}

cmd_default() {
    banner
    ensure_env

    echo -e "${CYAN}📋 Quick Commands:${NC}"
    echo -e "${GRAY}   ./verantyx-start.sh setup    — 初回セットアップ${NC}"
    echo -e "${GRAY}   ./verantyx-start.sh start    — Gateway起動${NC}"
    echo -e "${GRAY}   ./verantyx-start.sh stop     — Gateway停止${NC}"
    echo -e "${GRAY}   ./verantyx-start.sh chat     — 対話開始${NC}"
    echo -e "${GRAY}   ./verantyx-start.sh status   — 状態表示${NC}"
    echo -e "${GRAY}   ./verantyx-start.sh memory   — 記憶一覧${NC}"
    echo -e "${GRAY}   ./verantyx-start.sh inject   — 記憶注入プレビュー${NC}"
    echo -e "${GRAY}   ./verantyx-start.sh vfs      — VFS一覧${NC}"
    echo ""

    show_status
}

# コマンドルーティング
case "${1:-}" in
    setup)    cmd_setup ;;
    start)    cmd_start ;;
    stop)     cmd_stop ;;
    chat)     cmd_chat ;;
    status)   banner; ensure_env; auto_freshness_check; show_status ;;
    memory)   ensure_env; node openclaw.mjs spatial list 2>&1 | grep -v "Config was" | grep -v "🦞" ;;
    inject)   ensure_env; node openclaw.mjs spatial inject 2>&1 | grep -v "Config was" | grep -v "🦞" ;;
    vfs)      ensure_env; node openclaw.mjs vfs list 2>&1 | grep -v "Config was" | grep -v "🦞" ;;
    freshness) ensure_env; node openclaw.mjs spatial freshness 2>&1 | grep -v "Config was" | grep -v "🦞" ;;
    *)        cmd_default ;;
esac
