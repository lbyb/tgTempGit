# 豆瓣丛书AA搜索工具 - 安装和运行教程

## 一、环境准备

### 1.1 安装uv（Python包管理工具）

```bash
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用pip安装
pip install uv
```

### 1.2 项目结构
创建项目文件夹并准备以下文件：

```
douban-aa-search/
├── app.py           # 主程序文件（上面提供的代码）
├── pyproject.toml   # 项目配置文件
└── README.md        # 项目说明（可选）
```

## 二、配置文件

### 2.1 创建 pyproject.toml

```toml
[project]
name = "douban-aa-search"
version = "0.2.0"
description = "豆瓣丛书批量搜索AA工具"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.116.1",
    "uvicorn[standard]>=0.35.0",
    "httpx>=0.28.1",
    "beautifulsoup4>=4.13.0",
    "lxml>=5.0.0",
]

[tool.uv]
dev-dependencies = [
    "debugpy>=1.8.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

## 三、安装和运行

### 3.1 初始化项目环境

```bash
# 进入项目目录
cd douban-aa-search

# 使用uv创建虚拟环境并安装依赖
uv venv
uv pip install -r pyproject.toml

# 或者一步到位
uv sync
```

### 3.2 运行服务

#### 方法1：直接使用uv运行
```bash
# 开发模式（支持热重载）
uv run uvicorn app:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uv run uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

#### 方法2：激活虚拟环境后运行
```bash
# Windows
.venv\Scripts\activate
python app.py

# macOS/Linux
source .venv/bin/activate
python app.py
```

#### 方法3：使用Python直接运行
```bash
# 如果app.py包含了 if __name__ == "__main__": 部分
uv run python app.py
```

## 四、Docker部署（可选）

### 4.1 创建 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装uv
RUN pip install uv

# 复制项目文件
COPY pyproject.toml app.py ./

# 安装依赖
RUN uv venv && uv pip install -r pyproject.toml

# 暴露端口
EXPOSE 8000

# 运行应用
CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 4.2 构建和运行Docker容器

```bash
# 构建镜像
docker build -t douban-aa-search .

# 运行容器
docker run -d -p 8000:8000 --name douban-search douban-aa-search
```

## 五、使用说明

### 5.1 访问服务
服务启动后，在浏览器访问：
- 本地访问：`http://localhost:8000`
- 远程访问：`http://你的服务器IP:8000`

### 5.2 功能使用

#### 单个丛书搜索
1. 输入豆瓣丛书URL，如：`https://book.douban.com/series/1300`
2. 点击"合并搜索结果"
3. 等待处理完成（会显示进度）
4. 自动跳转到结果页面

#### 多个丛书批量搜索
1. 输入多个URL，用逗号分隔：
   ```
   https://book.douban.com/series/1300,https://book.douban.com/series/1301,https://book.douban.com/series/1302
   ```
2. 系统会依次处理，每个series之间延时60秒
3. 进度页面会显示当前处理到第几个series
4. 全部完成后显示合并的搜索结果

#### ISBN直接搜索
1. 输入ISBN号码，逗号或空格分隔
2. 点击搜索，直接返回结果（无需等待）

## 六、常见问题解决

### 6.1 端口被占用
```bash
# 更改端口为8080
uv run uvicorn app:app --port 8080
```

### 6.2 无法访问外网
检查防火墙设置：
```bash
# Linux防火墙开放端口
sudo ufw allow 8000

# 或使用iptables
sudo iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
```

### 6.3 豆瓣访问受限
- 程序已包含Cookie获取和重试机制
- 如果持续403错误，可能需要：
  1. 更换服务器IP
  2. 增加请求延时
  3. 使用代理

### 6.4 内存占用问题
任务结果默认存储在内存中，会自动清理2小时前的任务。
如需长期运行，建议：
1. 定期重启服务
2. 或修改代码使用Redis存储

## 七、性能优化建议

### 7.1 生产环境配置
```bash
# 使用多进程提升性能
uv run uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4

# 或使用gunicorn
uv pip install gunicorn
uv run gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 7.2 使用Nginx反向代理
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
    }
}
```

## 八、监控和日志

### 8.1 查看运行日志
```bash
# 实时查看日志
uv run uvicorn app:app --log-level info

# 保存日志到文件
uv run uvicorn app:app --log-level info 2>&1 | tee app.log
```

### 8.2 使用systemd管理（Linux）

创建服务文件 `/etc/systemd/system/douban-search.service`:

```ini
[Unit]
Description=Douban AA Search Service
After=network.target

[Service]
Type=exec
User=your-username
WorkingDirectory=/path/to/douban-aa-search
ExecStart=/usr/local/bin/uv run uvicorn app:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl start douban-search
sudo systemctl enable douban-search  # 开机自启
sudo systemctl status douban-search  # 查看状态
```

## 九、API测试

### 9.1 命令行测试
```bash
# 测试健康检查
curl http://localhost:8000/healthz

# 获取任务状态（替换task_id）
curl http://localhost:8000/task/your-task-id

# 使用HTTPie（更友好的输出）
pip install httpie
http GET localhost:8000/healthz
```

### 9.2 Python测试脚本
```python
import requests

# 提交搜索任务
response = requests.get("http://localhost:8000/search", params={
    "series_url": "https://book.douban.com/series/1300"
})
print(response.status_code)
```

## 十、更新和维护

### 10.1 更新代码后重新部署
```bash
# 停止当前服务
# 如果使用systemd
sudo systemctl stop douban-search

# 更新代码
git pull  # 如果使用git

# 更新依赖
uv sync

# 重启服务
sudo systemctl start douban-search
```

### 10.2 备份任务数据（如果需要）
由于任务数据存储在内存中，重启会丢失。
如需持久化，可以修改代码使用数据库或Redis。

---

## 快速开始命令汇总

```bash
# 1. 安装uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 创建项目
mkdir douban-aa-search && cd douban-aa-search

# 3. 创建文件（app.py和pyproject.toml）
# 复制上述代码到对应文件

# 4. 安装并运行
uv sync
uv run uvicorn app:app --reload --host 0.0.0.0 --port 8000

# 5. 访问 http://localhost:8000
```
