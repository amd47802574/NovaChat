# NovaChat v1.0.0 发布说明（Release Notes）

> 发布日期：2026-10-28
> 版本号：v1.0.0
> 仓库：https://github.com/amd47802574/NovaChat

## 一、版本结论与发布形态

NovaChat 是一个**基于 Corrective RAG 的智能知识问答平台**（Python/FastAPI 后端 + Vue3/Vite 前端），
其运行强依赖 **Milvus 向量库（etcd + minio + standalone）+ PostgreSQL + Redis** 三套基础设施，
且需要外部大模型 API Key。

基于上述架构，本项目**不具备打包为"双击即装"原生桌面安装包（.exe / .dmg / .AppImage）的条件**——
Milvus 为分布式向量数据库、体积与依赖沉重，无法像普通桌面软件一样被塞进单一安装包，
且应用本身当前也未引入 Electron / Tauri 等桌面框架。

因此本版本采用**对终端用户最友好、且唯一可行的发布形态**：

| 项目 | 内容 |
| --- | --- |
| **目标平台** | Windows 10/11（Docker Desktop）、macOS 12+、Ubuntu 20.04+（Docker Engine） |
| **安装包形式** | **Docker Compose 一键部署包**（跨平台容器发行）；附带**原生运行包**作为开发者备选 |
| **交付物** | `NovaChat-v1.0.0-release.zip`（含预构建前端、Dockerfile、发布编排、启动脚本、本说明） |
| **访问方式** | 启动后浏览器打开 `http://localhost:8000` |

> 若未来需要"双击安装、开箱即用"的真·桌面客户端，需将 Milvus 替换为可嵌入的向量引擎
> （如 Chroma / 本地 FAISS / SQLite-VSS），并用 Electron/Tauri 包裹前端 + 本地后端进程。
> 详见文末"缺失项与后续工作"。

## 二、本版本包含的发布配置（均为新增/补齐）

- `VERSION`：统一版本号文件（1.0.0）。
- `Dockerfile`：多阶段构建——Node 构建前端 `frontend/dist`，Python + uv 运行后端并静态托管前端。
- `.dockerignore`：裁剪构建上下文，避免把 `node_modules` / `.venv` / `data` 等带入镜像。
- `docker-compose.release.yml`：**在原有基础设施之上补齐 `app` 服务**，实现一条命令拉起整套系统。
- `start-docker.sh` / `start-docker.bat`：Docker 一键启动脚本（跨平台）。
- `start.sh` / `start.bat`：原生（非容器）运行脚本，遵循仓库约定用 `uv sync` 管理依赖。
- `pyproject.toml`：版本由 `0.1.0` 统一提升至 `1.0.0`（与前端 `package.json` 的 1.0.0 对齐）。
- `frontend/dist/`：已执行 `npm run build` 生产构建（经 `vue-tsc` 类型检查通过），随包分发。

## 三、安装与启动

### 方式 A（推荐）：Docker 一键部署

前置：安装并启动 Docker Desktop（Windows/macOS）或 Docker Engine（Linux）。

```bash
# 1) 解压发布包后进入目录
unzip NovaChat-v1.0.0-release.zip && cd NovaChat

# 2) 准备配置（按需编辑 API Key / 模型名）
cp .env.example .env

# 3) 一键拉起应用 + Milvus + PostgreSQL + Redis
docker compose -f docker-compose.release.yml up -d --build

# 4) 浏览器访问
#    http://localhost:8000        （NovaChat 主界面）
#    http://localhost:8080        （Milvus 可视化管理 Attu，可选）
```

### 方式 B：原生运行（仅用 Docker 跑基础设施，应用本地运行）

```bash
# 1) 先启动基础设施
docker compose up -d        # 仅 Milvus/PG/Redis

# 2) 准备配置与依赖
cp .env.example .env
uv sync                     # 项目含 pyproject.toml，优先 uv sync

# 3) 启动后端（前端已由 npm run build 产物在 http://localhost:8000 托管）
uv run uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

## 四、必填配置（`.env`）

| 变量 | 说明 | 是否必填 |
| --- | --- | --- |
| `ARK_API_KEY` | 大模型 API Key（DeepSeek / 兼容 OpenAI 协议） | **必填** |
| `BASE_URL` | 模型服务地址，默认 `https://api.deepseek.com/v1` | 必填 |
| `MODEL` | 主力对话模型名 | 必填 |
| `EMBEDDING_MODEL` | 本地稠密向量模型，默认 `sentence-transformers/all-MiniLM-L6-v2` | 必填（首次需联网下载） |
| `JWT_SECRET_KEY` | 登录鉴权密钥，**请改为随机强密钥** | 必填 |
| `ADMIN_INVITE_CODE` | 管理员注册邀请码 | 必填 |
| `RERANK_API_KEY` | Jina Rerank 精排 Key（不填则自动降级为 RRF） | 可选 |
| `FIRECRAWL_API_KEY` | 网络搜索 Key（默认 firecrawl；可改 duckduckgo 免费） | 可选 |

> ⚠️ **首次启动联网提示**：`.env` 中 `HF_HUB_OFFLINE` 默认 `1`（离线，避免启动卡死）。
> 镜像内 `docker-compose.release.yml` 已将该值覆盖为 `0`，以便**首次运行自动下载嵌入模型**；
> 模型下载完成后可改回 `1` 以加速启动。

## 五、构建产物校验（本机已验证）

- 前端生产构建：`npm ci && npm run build` → 成功生成 `frontend/dist/`（约 2.5 MB，含 `index.html` 与 `assets/`）。
- 版本一致性：`pyproject.toml` 与 `frontend/package.json` 均为 `1.0.0`。

## 六、已知问题 / 限制

1. **必须联网下载嵌入模型**：首次运行需可访问 HuggingFace（或 `HF_ENDPOINT` 镜像）。完全离线环境需预先把模型放入 HF 缓存卷。
2. **资源占用**：Milvus standalone 建议至少 2 核 4GB 内存；低配机器可能启动缓慢。
3. **无自动建库脚本纳入启动**：集合（Collection）由后端 `ensure_collection` 在首次写入/检索时按需创建；如需提前建库可运行 `python create_collection.py`（需 Milvus 已就绪）。
4. **`HOST`/`PORT` 环境变量**：后端默认 `0.0.0.0:8000`，如需改端口请改启动命令或环境变量。

## 七、缺失项与后续工作（需补充才能更"开箱即用"）

| 缺失项 | 影响 | 建议补充 |
| --- | --- | --- |
| 真·桌面安装器（NSIS/InnoSetup/electron-builder） | 无法双击安装 | 引入 Tauri/Electron + 可嵌入向量库 |
| 应用 Dockerfile（已在本版补齐） | 原仓库仅有基础设施 compose | ✅ 已完成 |
| compose 中的 app 服务（已在本版补齐） | 原 `docker-compose.prod.yml` 不含应用 | ✅ 已完成 |
| 统一 `CHANGELOG.md` | 更新日志仅散落在 README | 建议抽取为独立文件 |
| GitHub Actions CI/CD | 无自动化构建与发布 | 建议增加 workflow 自动打镜像/出包 |
| 嵌入模型预置或离线包 | 首次必须联网 | 提供模型离线包或镜像内预下载 |
| 健康检查 `/healthz` | 容器依赖 `service_healthy` 仅对基础设施 | 建议后端增加健康检查端点供 `app` 探活 |

## 八、升级说明

从早期源码升级到 v1.0.0：
1. 拉取本发布包，覆盖 `Dockerfile` / `docker-compose.release.yml` / 启动脚本。
2. 保留已有 `volumes/`（PostgreSQL / Redis / Milvus 数据持久化），勿删除。
3. 重新 `docker compose -f docker-compose.release.yml up -d --build` 即可；集合 Schema 具备自动升级能力。
