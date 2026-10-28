#!/usr/bin/env bash
# NovaChat v1.0.0 —— Docker 一键启动（推荐）
# 适用：Windows 10/11 (Docker Desktop)、macOS 12+、Ubuntu 20.04+ (Docker Engine)
set -e

# 1) 准备环境变量文件（按需编辑 API Key / 模型名）
if [ ! -f .env ]; then
  cp .env.example .env
  echo "已生成 .env，请用编辑器填入 ARK_API_KEY / MODEL / BASE_URL 等必填项。"
fi

# 2) 拉起全部服务（应用 + Milvus + PostgreSQL + Redis）
docker compose -f docker-compose.release.yml up -d --build

echo ""
echo "=========================================================="
echo "NovaChat 启动完成。"
echo "  访问地址 : http://localhost:8000"
echo "  Milvus管理(Attu): http://localhost:8080"
echo "  查看日志 : docker compose -f docker-compose.release.yml logs -f app"
echo "  停止服务 : docker compose -f docker-compose.release.yml down"
echo "=========================================================="
