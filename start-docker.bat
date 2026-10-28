@echo off
REM NovaChat v1.0.0 -- Docker one-click launcher (recommended)
REM Requires: Docker Desktop installed and running

if not exist ".env" (
  copy .env.example .env
  echo Created .env. Please edit ARK_API_KEY / MODEL / BASE_URL before first run.
)

docker compose -f docker-compose.release.yml up -d --build

echo.
echo ==========================================================
echo  NovaChat is starting.
echo  Web UI      : http://localhost:8000
echo  Milvus (Attu): http://localhost:8080
echo  Stop        : docker compose -f docker-compose.release.yml down
echo ==========================================================
pause
