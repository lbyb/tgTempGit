---
name: docker
description: Docker best practices and conventions. Use when creating Dockerfiles, docker-compose files, containerizing applications, or troubleshooting Docker builds and deployments.
---

# Docker 最佳实践

## Dockerfile 规范

### 基础镜像选择

- 优先使用官方镜像的 slim/alpine 变体以减小体积
- 固定镜像版本标签（如 `python:3.12-slim`），避免使用 `latest`

```dockerfile
FROM python:3.12-slim AS builder
```

### 多阶段构建（Multi-stage Build）

将构建阶段与运行阶段分离：

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 层级优化

- 将不常变动的指令放在前面（如安装系统依赖）
- 将频繁变更的指令放在后面（如复制应用代码）
- 合并 RUN 指令减少层数：

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*
```

### 安全实践

- 不使用 root 用户运行应用：

```dockerfile
RUN addgroup --system app && adduser --system --group app
USER app
```

- 使用 `.dockerignore` 排除不必要文件：

```
__pycache__
*.pyc
.git
.env
venv/
.vscode/
node_modules/
```

### 健康检查

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
```

## Docker Compose

### 服务定义

```yaml
version: "3.9"

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/mydb
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: mydb
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d mydb"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

### compose 命令

```bash
# 构建并启动
docker compose up --build -d

# 查看日志
docker compose logs -f app

# 进入服务容器
docker compose exec app /bin/sh

# 停止并清理
docker compose down -v
```

## 常用命令

```bash
# 构建镜像
docker build -t myapp:latest -f Dockerfile .

# 查看镜像层
docker history myapp:latest

# 清理无用资源
docker system prune -a --volumes

# 查看容器资源占用
docker stats
```

## 镜像大小优化

- 使用 `--no-cache-dir` 避免缓存 pip 包
- 清理 apt 缓存：`rm -rf /var/lib/apt/lists/*`
- 使用 `.dockerignore` 排除大文件
- 考虑使用 `python:3.12-alpine`（需注意 musl 兼容性）
