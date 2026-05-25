---
name: uvicorn
description: Uvicorn ASGI server configuration and deployment. Use when configuring Uvicorn settings, deploying FastAPI/Starlette apps in production, tuning worker processes, or integrating with Gunicorn.
---

# Uvicorn 配置与部署

## 开发环境

```bash
# 热重载模式
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 等同于 fastapi dev（内部调用 uvicorn）
fastapi dev app/main.py
```

## 生产环境

### 单机部署

```bash
uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --log-level info \
    --proxy-headers \
    --forwarded-allow-ips '*'
```

### 与 Gunicorn 配合

```bash
gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
```

Gunicorn 配置（`gunicorn.conf.py`）：

```python
import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
```

## 代码内启动

```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,           # 仅开发
        log_level="info",
    )
```

## 常用配置参数

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `--host` | 绑定地址 | `0.0.0.0` |
| `--port` | 绑定端口 | `8000` |
| `--workers` | 工作进程数 | `cpu * 2 + 1` |
| `--reload` | 热重载（仅开发） | 生产禁用 |
| `--proxy-headers` | 信任反向代理头 | 生产启用 |
| `--limit-concurrency` | 最大并发连接 | 按需设置 |
| `--timeout-keep-alive` | Keep-Alive 超时 | `5`（秒） |

## Docker 部署

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
```

compose 中的健康检查：

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 5s
  retries: 3
```

## 性能调优

- **Workers**：CPU 密集型任务使用 `cpu_count * 2 + 1`，IO 密集型可更高
- **limit-max-requests**：设置 worker 处理 N 个请求后重启，防止内存泄漏
- **backlog**：`--backlog 2048` 增大 TCP 连接队列
- **uvloop**：安装 `uvicorn[standard]` 自动启用 uvloop

```bash
uvicorn app.main:app \
    --workers 4 \
    --limit-max-requests 10000 \
    --backlog 2048 \
    --limit-concurrency 1000
```
