# run.ps1 — douban-aa-search Windows 一键部署
$ErrorActionPreference = "Stop"

$PORT = if ($args.Count -gt 0) { $args[0] } else { "24518" }

Write-Host "[INFO] 检查 Docker..." -ForegroundColor Green
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Docker 未安装，请安装 Docker Desktop: https://www.docker.com/products/docker-desktop/" -ForegroundColor Red
    exit 1
}
Write-Host "[INFO] Docker 已安装 ($(docker --version))" -ForegroundColor Green

$COMPOSE_FILE = ""
if (Test-Path "compose.yaml") { $COMPOSE_FILE = "compose.yaml" }
elseif (Test-Path "compose.yml") { $COMPOSE_FILE = "compose.yml" }
else { Write-Host "[ERROR] 未找到 compose.yaml" -ForegroundColor Red; exit 1 }

$REQUIRED = @("Dockerfile", "nginx.conf", "supervisord.conf", "pyproject.toml")
foreach ($f in $REQUIRED) {
    if (-not (Test-Path $f)) { Write-Host "[ERROR] 缺少文件: $f" -ForegroundColor Red; exit 1 }
}

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR
Write-Host "[INFO] 工作目录: $SCRIPT_DIR" -ForegroundColor Green

Write-Host ""
Write-Host "[INFO] 停止并清除旧容器..." -ForegroundColor Green
docker compose -f $COMPOSE_FILE down 2>$null

Write-Host ""
Write-Host "[INFO] 构建镜像..." -ForegroundColor Green
docker compose -f $COMPOSE_FILE build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[INFO] 启动容器..." -ForegroundColor Green
docker compose -f $COMPOSE_FILE up -d

Write-Host ""
Write-Host "[INFO] 服务已启动!" -ForegroundColor Green
Write-Host "  访问地址: http://localhost:${PORT}"
Write-Host ""
Write-Host "  常用命令:"
Write-Host "    日志  : docker compose logs -f"
Write-Host "    停止  : docker compose down"
Write-Host "    重启  : docker compose restart"
