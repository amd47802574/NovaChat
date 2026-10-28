# ============================================================
# NovaChat 应用镜像（多阶段构建）
# Stage 1: 用 Node 构建前端生产产物 frontend/dist
# Stage 2: 用 Python + uv 运行 FastAPI 后端，并静态托管前端
# ============================================================

# ---------- Stage 1: 前端构建 ----------
FROM node:22-slim AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: 运行时 ----------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# 系统依赖：psycopg2 编译、antiword/LibreOffice 文档解析降级链所需基础库
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（项目指定包管理器）
COPY https://astral.sh/uv/install.sh /tmp/uv-install.sh
RUN sh /tmp/uv-install.sh && rm /tmp/uv-install.sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# 先装 Python 依赖（利用缓存层：依赖变动频率远低于代码）
COPY pyproject.toml uv.lock ./
COPY backend/ ./backend/
RUN uv sync --frozen

# 再拷贝前端构建产物与启动模板
COPY --from=frontend-builder /build/dist ./frontend/dist
COPY .env.example ./.env.example
COPY create_collection.py ./

EXPOSE 8000

# 生产入口：通过 uvicorn 运行 FastAPI；前端由后端在 / 静态托管
CMD ["uv", "run", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
