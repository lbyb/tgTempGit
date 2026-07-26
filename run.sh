#!/usr/bin/env bash
set -euo pipefail

# ╔══════════════════════════════════════════════════════════════════════╗
# ║                    run.sh — cfCloudFile 一键管理脚本                  ║
# ╠══════════════════════════════════════════════════════════════════════╣
# ║                                                                      ║
# ║  快速上手:                                                           ║
# ║    ./run.sh                   首次/日常启动（智能增量构建，快）       ║
# ║    ./run.sh deploy            git pull 后完整重建部署（--no-cache）    ║
# ║    ./run.sh debug             调试模式，端口 32642                    ║
# ║                                                                      ║
# ║  访问地址（启动后）:                                                 ║
# ║    主页:    http://localhost/?token=lby                               ║
# ║    API文档: http://localhost/docs?token=lby                           ║
# ║    健康检查: http://localhost/health                                  ║
# ║                                                                      ║
# ║  子命令:                                                             ║
# ║    up         启动（增量构建，默认）    restart     重启服务          ║
# ║    deploy     完整重建（git pull 后用） build       仅构建不启动      ║
# ║    debug      调试模式（端口 32642）    down        停止并删除        ║
# ║    logs       查看实时日志              status      查看服务状态      ║
# ║    help       显示此帮助                                            ║
# ║                                                                      ║
# ║  Docker 备忘:                                                        ║
# ║    docker compose ps                查看容器状态                     ║
# ║    docker compose logs -f app       查看 app 日志                    ║
# ║    docker compose exec app /bin/sh  进入 app 容器                    ║
# ║    docker compose down -v           停止并清理（含数据卷）            ║
# ║    docker system prune -a           清理所有未使用资源                ║
# ║                                                                      ║
# ╚══════════════════════════════════════════════════════════════════════╝

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "\n${CYAN}──▶${NC} ${BOLD}$*${NC}"; }

# ══════════════════════════════════════════════════════════════════════════
# 环境检测
# ══════════════════════════════════════════════════════════════════════════

SUBCOMMAND="${1:-up}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Docker
if ! command -v docker &>/dev/null; then
    log_error "Docker 未安装 → https://docs.docker.com/engine/install/"
    exit 1
fi
log_info "Docker $(docker --version | cut -d' ' -f3 | tr -d ',')"

DOCKER_INFO=$(docker info 2>&1)
if [[ $? -ne 0 ]]; then
    if echo "$DOCKER_INFO" | grep -q "permission denied"; then
        log_error "无权限 → sudo usermod -aG docker \$USER && newgrp docker"
    else
        log_error "Docker 守护进程未运行"
    fi
    exit 1
fi

# Compose 文件
COMPOSE_FILE=""
for f in docker-compose.yml compose.yml compose.yaml; do
    [[ -f "$f" ]] && { COMPOSE_FILE="$f"; break; }
done
[[ -z "$COMPOSE_FILE" ]] && { log_error "未找到 compose 文件"; exit 1; }
log_info "compose 文件: $COMPOSE_FILE"

# Compose 命令
COMPOSE_CMD=""
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    log_error "未找到 Docker Compose"
    exit 1
fi
log_info "compose 命令: $COMPOSE_CMD"

# 必要文件
for f in "backend/Dockerfile" "frontend/package.json" "$COMPOSE_FILE"; do
    [[ -f "$f" ]] || { log_error "未找到 $f"; exit 1; }
done
for d in "backend" "frontend"; do
    [[ -d "$d" ]] || { log_error "未找到 $d/"; exit 1; }
done
log_info "项目文件检查通过 ✓"

# ══════════════════════════════════════════════════════════════════════════
# 子命令实现
# ══════════════════════════════════════════════════════════════════════════

# ── 打印启动成功信息（每次 up/deploy 后都会显示） ──
print_banner() {
    local port="${1:-80}"
    local TOKEN
    TOKEN=$(grep TOKEN= .env 2>/dev/null | cut -d= -f2 || echo "lby")
    local BASE_URL="http://localhost"
    [[ "$port" != "80" ]] && BASE_URL="${BASE_URL}:${port}"

    echo ""
    printf "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    printf "${CYAN}${BOLD}         cfCloudFile 启动成功${NC}\n"
    printf "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    echo ""
    echo -e "  ${BOLD}主页${NC}       ${BOLD}${BASE_URL}/?token=${TOKEN}${NC}"
    echo -e "  ${BOLD}API 文档${NC}   ${BASE_URL}/docs?token=${TOKEN}"
    echo -e "  ${BOLD}健康检查${NC}   ${BASE_URL}/health"
    echo ""
    printf "${YELLOW}  Cloudflare: 将域名 A 记录指向本机 IP，代理（橙云）或 DNS（灰云）均可${NC}\n"
    echo ""

    # ── Docker 常用命令速查 ──
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━ 常用 Docker 命令 ━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  ${YELLOW}查看日志${NC}     ${GREEN}$COMPOSE_CMD logs -f app${NC}"
    echo -e "  ${YELLOW}服务状态${NC}     ${GREEN}$COMPOSE_CMD ps${NC}                   ${YELLOW}资源占用${NC}   ${GREEN}docker stats${NC}"
    echo -e "  ${YELLOW}进入容器${NC}     ${GREEN}$COMPOSE_CMD exec app /bin/sh${NC}     ${YELLOW}重启服务${NC}   ${GREEN}$COMPOSE_CMD restart${NC}"
    echo -e "  ${YELLOW}停止服务${NC}     ${GREEN}$COMPOSE_CMD down${NC}                 ${YELLOW}清理(含数据)${NC}${GREEN} $COMPOSE_CMD down -v${NC}"
    echo -e "  ${YELLOW}完整重建${NC}     ${GREEN}./run.sh deploy${NC}                   ${YELLOW}调试模式${NC}   ${GREEN}./run.sh debug${NC}"
    echo -e "  ${YELLOW}清理闲置${NC}     ${GREEN}docker system prune -a${NC}"
    echo ""
    echo -e "  重新查看本提示:  ${GREEN}./run.sh help${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

# ── 启动核心逻辑 ──
do_up() {
    local port="${1:-80}"
    local full_rebuild="${2:-false}"   # true = --no-cache 完整重建

    export APP_PORT="$port"

    # .env
    if [[ ! -f .env ]]; then
        cp .env.example .env
        log_info "已创建 .env（默认配置，编辑 .env 可修改 token/密码/大小限制）"
    fi

    # 停止旧容器
    local running
    running=$($COMPOSE_CMD -f "$COMPOSE_FILE" ps -q 2>/dev/null)
    if [[ -n "$running" ]]; then
        log_info "停止旧容器..."
        $COMPOSE_CMD -f "$COMPOSE_FILE" down
    fi

    # 拉取基础镜像
    log_step "拉取基础镜像"
    $COMPOSE_CMD -f "$COMPOSE_FILE" pull --ignore-buildable 2>/dev/null || true

    # 构建
    if $full_rebuild; then
        log_step "完整重建镜像（--no-cache，git pull 后推荐）"
        $COMPOSE_CMD -f "$COMPOSE_FILE" build --no-cache
    else
        log_step "增量构建镜像（仅重建变更部分，缓存加速）"
        $COMPOSE_CMD -f "$COMPOSE_FILE" build
    fi

    # 启动
    log_step "启动容器（端口 ${port}）"
    $COMPOSE_CMD -f "$COMPOSE_FILE" up -d

    # 等数据库
    log_info "等待数据库就绪..."
    local i=0
    while [[ $i -lt 30 ]]; do
        if $COMPOSE_CMD -f "$COMPOSE_FILE" exec db pg_isready -U cfcloud -d cfcloud &>/dev/null; then
            break
        fi
        sleep 1; i=$((i + 1))
    done

    # 等应用
    log_info "等待应用启动..."
    i=0
    while [[ $i -lt 30 ]]; do
        if curl -sf "http://localhost:${port}/health" &>/dev/null; then
            break
        fi
        sleep 1; i=$((i + 1))
    done
    [[ $i -ge 30 ]] && log_warn "启动超时 → $COMPOSE_CMD logs app"

    print_banner "$port"
}

cmd_up()     { do_up 80 false; }
cmd_deploy() { do_up 80 true;  }
cmd_debug()  { do_up 32642 true; }

cmd_down() {
    log_info "停止并删除服务..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" down
    log_info "已停止 ✓"
}

cmd_restart() {
    log_info "重启服务..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" restart
    log_info "已重启 ✓"
    print_banner
}

cmd_logs()   { $COMPOSE_CMD -f "$COMPOSE_FILE" logs -f app; }
cmd_status() { $COMPOSE_CMD -f "$COMPOSE_FILE" ps; }

cmd_build() {
    log_step "增量构建镜像"
    $COMPOSE_CMD -f "$COMPOSE_FILE" build
    log_info "构建完成 ✓"
}

cmd_help() {
    echo ""
    echo "用法: ./run.sh [命令]"
    echo ""
    echo "命令:"
    echo "  up         日常启动（增量构建，利用 Docker 缓存，快速）"
    echo "  deploy     git pull 后完整重建（--no-cache）"
    echo "  debug      调试模式（端口 32642）"
    echo "  down       停止并删除服务"
    echo "  restart    重启服务"
    echo "  logs       查看 app 实时日志"
    echo "  status     查看容器运行状态"
    echo "  build      仅增量构建镜像，不启动"
    echo "  help       显示此帮助"
    echo ""
    echo "场景:"
    echo "  ./run.sh                  # 日常启动，改动小 → 快"
    echo "  git pull && ./run.sh deploy  # 拉代码后完整重建"
    echo "  ./run.sh debug            # 调试端口 32642"
    echo ""
    echo "访问:"
    echo "  http://localhost/?token=lby          主页"
    echo "  http://localhost/docs?token=lby      API 文档"
    echo "  http://localhost/health              健康检查"
    echo ""
    echo "Docker 备忘:"
    echo "  docker compose ps                   容器状态"
    echo "  docker compose logs -f app          应用日志"
    echo "  docker compose exec app /bin/sh     进入容器"
    echo "  docker compose down -v              停止+清数据"
    echo "  docker system prune -a              清理未使用资源"
    echo ""
}

# ══════════════════════════════════════════════════════════════════════════
# 命令分发
# ══════════════════════════════════════════════════════════════════════════

case "$SUBCOMMAND" in
    up)            cmd_up ;;
    deploy)        cmd_deploy ;;
    debug)         cmd_debug ;;
    down)          cmd_down ;;
    restart)       cmd_restart ;;
    logs)          cmd_logs ;;
    status)        cmd_status ;;
    build)         cmd_build ;;
    help|--help|-h) cmd_help ;;
    *)
        log_error "未知命令: $SUBCOMMAND"
        echo "  ./run.sh help    查看帮助"
        exit 1
        ;;
esac
