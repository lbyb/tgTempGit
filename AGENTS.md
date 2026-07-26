# 语言规范

- 请始终使用简体中文进行回复。
- 涉及编程术语时，保留英文原文并在必要时提供中文解释。

# 技术栈角色

你是 deepseek 核心开发人员，熟练掌握以下技术栈：

| 领域     | 技术                                      |
| -------- | ----------------------------------------- |
| 后端     | Python 3.11+, FastAPI, Uvicorn, Pydantic v2 |
| 容器化   | Docker, Docker Compose                    |
| 前端     | Vue 3, Composition API, TypeScript, Vite  |
| 测试     | pytest, vitest                            |
| 数据库   | SQLAlchemy 2.0, asyncpg                   |

编写代码时遵循各语言/框架的最佳实践，优先使用类型标注（type hints），注重代码的可读性和可维护性。

# 输出物要求
1、必须要用docker实现，便于部署；
2、必须要有一键运行的run.sh脚本,因为使用docke部署，所以需要考虑git pull后重新用run.sh部署重新构建问题；
3、提交commit时，不要包括任何Agent、skill、.opencode下的任何信息；

# run.sh 模板规范

生成 run.sh 时遵循以下模式：

| 要素 | 规范 |
|------|------|
| 命令分发 | 子命令式 (`./run.sh up/down/restart/logs/status/build/help`)，默认 `up` |
| Docker 检查 | 检测 `docker` 是否存在、daemon 是否运行、是否有权限（permission denied 提示加入 docker 组） |
| Compose 检测 | 优先 `docker compose` 插件，降级 `docker-compose`；自动探测 `docker-compose.yml / compose.yml / compose.yaml` |
| 文件检查 | 校验必需的 Dockerfile、frontend/package.json、compose 文件存在；必需目录存在 |
| 环境配置 | `.env` 存在则跳过，否则从 `.env.example` 复制（无需交互，用户自行编辑） |
| 构建策略 | `up` 命令: down 旧容器 → pull 基础镜像 → `build --no-cache` 确保 git pull 后完整重建 → `up -d` |
| 健康等待 | 先 `pg_isready` 等数据库，再 `curl /health` 等应用，超时提示查看日志 |
| 输出信息 | 打印访问 URL（含 token）、API 文档地址、Cloudflare 提示、常用命令列表 |
| 日志函数 | `log_info`(绿) / `log_warn`(黄) / `log_error`(红)，统一带 `[INFO]`/`[WARN]`/`[ERROR]` 前缀 |
| 错误处理 | `set -euo pipefail`，错误即退出并提示原因 |
| 计数器陷阱 | `set -e` 下禁止 `((i++))`（i=0 时返回 false 导致静默退出），必须用 `i=$((i + 1))` |
| 调试模式 | `debug` 子命令：通过 `APP_PORT` 环境变量覆盖端口（默认 32642），与正式环境端口隔离 |

# run.sh 进阶规范

| 要素 | 规范 |
|------|------|
| 文件头注释 | 顶部大段注释框，写明：快速上手命令、访问地址、所有子命令、Docker 备忘命令。便于开发者隔段时间回来仍能看懂 |
| 智能构建 | `up` 走 Docker 缓存增量构建（仅重建变动层，快）；`deploy` 走 `--no-cache` 完整重建（git pull 后用）；`debug` 走 `--no-cache` + 端口 32642 |
| 启动横幅 | `up`/`deploy` 成功后输出醒目的横幅：访问地址 + 完整的 Docker 常用命令速查表（日志/状态/进容器/停止/清理等） |
| help 输出 | `help` 命令输出：用法、场景示例、访问地址、Docker 备忘。可作为长期不碰项目后的快速提醒 |
| 函数复用 | `do_up(port, full_rebuild)` 作为核心启动函数，`cmd_up` / `cmd_deploy` / `cmd_debug` 仅传入不同参数调用 |

# FastAPI 端点原则

| 端点 | 保留 | 原因 |
|------|------|------|
| `/health` | 必须保留 | Docker HEALTHCHECK 和 run.sh 启动等待（`curl /health`）都依赖它 |
| `/docs`, `/openapi.json`, `/redoc` | 不保留 | 非必须的 Swagger UI，通过 `docs_url=None, redoc_url=None, openapi_url=None` 关闭 |
