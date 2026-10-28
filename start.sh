#!/usr/bin/env bash
# NovaChat v1.0.0 —— 原生运行（不使用应用容器，仅基础设施走 Docker）
# 前置：已执行 `docker compose up -d` 启动 Milvus/PostgreSQL/Redis
set -e

# 1) 环境变量
if [ ! -f .env ]; then
  cp .env.example .env
  echo "已生成 .env，请填入 ARK_API_KEY / MODEL / BASE_URL 等必填项。"
fi

# 2) 后端依赖（uv 隔离环境；项目含 pyproject.toml，优先使用 uv sync）
uv sync

# 3) 确保前端已构建（docker 发布包已预置 frontend/dist，此处为原生运行兜底）
if [ ! -d frontend/dist ]; then
  (cd frontend && npm ci && npm run build)
fi

# 4) 启动后端（前端由后端在 http://localhost:8000 静态托管）
uv run uvicorn backend.app:app --host 0.0.0.0 --port 8000
