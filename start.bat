@echo off
REM NovaChat v1.0.0 -- Native launcher (infra via Docker, app runs locally)
REM Prereq: run `docker compose up -d` first to start Milvus/PostgreSQL/Redis

if not exist ".env" (
  copy .env.example .env
  echo Created .env. Please fill ARK_API_KEY / MODEL / BASE_URL.
)

call uv sync

if not exist "frontend\dist" (
  cd frontend
  call npm ci
  call npm run build
  cd ..
)

call uv run uvicorn backend.app:app --host 0.0.0.0 --port 8000
pause
