FROM node:20-alpine AS build-frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --ignore-scripts 2>/dev/null || npm install --ignore-scripts
COPY frontend/ .
RUN npx vite build

FROM python:3.12-slim AS runtime
WORKDIR /app

RUN groupadd -r app && useradd -r -g app app
RUN mkdir -p /app/uploads && chown -R app:app /app

COPY --from=build-frontend /frontend/dist /app/backend/app/static
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/__init__.py /app/backend/__init__.py
COPY backend/app /app/backend/app

USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
