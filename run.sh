#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# run.sh — douban-aa-search 一键构建启动脚本
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

PORT="${1:-24518}"

# ── 1. 检查 Docker ──────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    log_error "Docker 未安装"
    echo "  请访问 https://docs.docker.com/engine/install/ 安装 Docker"
    exit 1
fi
log_info "Docker 已安装  ($(docker --version | cut -d' ' -f3 | tr -d ','))"

DOCKER_INFO=$(docker info 2>&1)
if [[ $? -ne 0 ]]; then
    if echo "$DOCKER_INFO" | grep -q "permission denied"; then
        log_error "无权限访问 Docker，请将当前用户加入 docker 组:"
        echo "    sudo usermod -aG docker \$USER && newgrp docker"
    else
        log_error "Docker 守护进程未运行，请启动 Docker 后重试"
    fi
    exit 1
fi
log_info "Docker 守护进程运行中"

# ── 2. 检测 Docker Compose 文件 ────────────────────────────
COMPOSE_FILE=""
if [[ -f "compose.yaml" ]]; then
    COMPOSE_FILE="compose.yaml"
elif [[ -f "compose.yml" ]]; then
    COMPOSE_FILE="compose.yml"
else
    log_error "未找到 compose.yaml 或 compose.yml"
    exit 1
fi

# ── 3. 检测 Docker Compose ──────────────────────────────────
COMPOSE_CMD=""
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
    log_info "使用 docker compose 插件"
elif command -v docker-compose &>/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
    log_info "使用 docker-compose (独立)"
else
    log_error "未找到 Docker Compose"
    echo "  请安装 docker compose 插件或 docker-compose"
    exit 1
fi

# ── 4. 必要文件检查 ─────────────────────────────────────────
REQUIRED_FILES=("Dockerfile" "nginx.conf" "supervisord.conf" "pyproject.toml")
for f in "${REQUIRED_FILES[@]}"; do
    if [[ ! -f "$f" ]]; then
        log_error "未找到必需文件: $f"
        exit 1
    fi
done

REQUIRED_DIRS=("backend")
for d in "${REQUIRED_DIRS[@]}"; do
    if [[ ! -d "$d" ]]; then
        log_error "未找到必需目录: $d"
        exit 1
    fi
done

# ── 5. 切换到脚本所在目录 ──────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
log_info "工作目录: $SCRIPT_DIR"

# ── 6. 停止旧容器并构建启动 ─────────────────────────────────
echo ""
log_info "停止并清除旧容器..."
$COMPOSE_CMD -f "$COMPOSE_FILE" down 2>/dev/null || true

echo ""
log_info "开始构建镜像..."
$COMPOSE_CMD -f "$COMPOSE_FILE" build

echo ""
log_info "启动容器..."
$COMPOSE_CMD -f "$COMPOSE_FILE" up -d

# ── 7. 启动完成 ─────────────────────────────────────────────
echo ""
log_info "服务已启动!"
echo "  访问地址: ${BOLD}http://localhost:${PORT}${NC}"
echo "  调试端口: ${BOLD}${PORT}${NC}（通过 Nginx 代理前端 + API）"

# ── 8. 显示常用命令 ────────────────────────────────────────
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}${BOLD}  常用 Docker Compose 命令${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  ${YELLOW}日志${NC}        ${GREEN}$COMPOSE_CMD logs -f${NC}"
echo -e "  ${YELLOW}状态${NC}        ${GREEN}$COMPOSE_CMD ps${NC}"
echo -e "  ${YELLOW}资源${NC}        ${GREEN}docker stats${NC}"
echo -e "  ${YELLOW}停止${NC}        ${GREEN}$COMPOSE_CMD down${NC}"
echo -e "  ${YELLOW}清理${NC}        ${GREEN}$COMPOSE_CMD down -v${NC}"
echo -e "  ${YELLOW}重启${NC}        ${GREEN}$COMPOSE_CMD restart${NC}"
echo -e "  ${YELLOW}重构建${NC}      ${GREEN}$COMPOSE_CMD up --build -d${NC}"
echo -e "  ${YELLOW}进容器${NC}      ${GREEN}$COMPOSE_CMD exec app /bin/bash${NC}"
echo -e "  ${YELLOW}镜像层${NC}      ${GREEN}docker history \$(docker compose images -q app)${NC}"
echo -e "  ${YELLOW}全清理${NC}      ${GREEN}docker system prune -a${NC}"
echo ""
