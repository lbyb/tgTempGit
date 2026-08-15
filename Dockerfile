# ============================================================
# 构建顺序说明（优化部署速度）
# - 慢且稳定的层（apt / pip / playwright chromium / 权限）
#   放在 backend 源码 COPY 之前，代码改动时这些层全部命中缓存
# - backend/、frontend/dist、nginx.conf、supervisord.conf 是易变层，
#   只在源码变化时重建
# ============================================================

FROM node:20-alpine AS frontend-builder

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci 2>/dev/null || npm install
ARG VITE_APP_TOKEN
ENV VITE_APP_TOKEN=$VITE_APP_TOKEN
COPY frontend/ ./
RUN npm run build


FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1

# ── 稳定依赖层：apt ─────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── 稳定依赖层：pip ─────────────────────────────────────────
# 注意：此处只 COPY pyproject.toml（不 COPY backend 源码），
# 保证 backend 代码改动不会使 pip 层缓存失效
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir fastapi "uvicorn[standard]" httpx beautifulsoup4 lxml requests playwright

# ── 稳定依赖层：Playwright Chromium ────────────────────────
# --with-deps 会通过 apt 安装 chromium 运行所需的系统库
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps chromium

# ── 权限层：app 用户 + chromium 可读可执行 ──────────────────
# 与 playwright 同层缓存；chmod 文件多较慢，仅首次/镜像重建时执行
RUN addgroup --system app && adduser --system --group app && \
    mkdir -p /var/log/supervisor && \
    chown -R app:app /var/log/supervisor && \
    chmod -R a+rx /ms-playwright

# ── 易变层：源码 / 静态资源 / 配置（代码改动只重建这几层）─
COPY backend/ ./backend/
COPY --from=frontend-builder /frontend/dist ./frontend/dist
COPY nginx.conf /etc/nginx/nginx.conf
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN chown -R app:app /app

EXPOSE 24518

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
