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

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/ ./backend/

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir fastapi "uvicorn[standard]" httpx beautifulsoup4 lxml requests

COPY --from=frontend-builder /frontend/dist ./frontend/dist

COPY nginx.conf /etc/nginx/nginx.conf
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN addgroup --system app && adduser --system --group app && \
    chown -R app:app /app && \
    mkdir -p /var/log/supervisor && \
    chown -R app:app /var/log/supervisor

EXPOSE 24518

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
