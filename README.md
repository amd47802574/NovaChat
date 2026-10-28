# NovaChat（星智问答）

NovaChat（星智问答）是一个基于 Corrective RAG 的智能知识问答平台，支持混合检索、结果重排、来源引用、多轮会话与知识库管理。

## Docker部署（不包含前后端，需额外启动）

封装了Milvus、Redis、Postgres，不包含前后端原因：方便随时更改模型及密钥

### 1) 环境准备

- Python `3.12+`
- 包管理建议：`uv`（也支持 `pip`）
- Docker / Docker Compose

### 2) 启动数据库、缓存和向量库服务

当前仓库的 `docker-compose.yml` 同时承载业务依赖与 Milvus 依赖：

- 业务依赖：`postgres`、`redis`
- 向量依赖：`etcd`、`minio`、`standalone`、`attu`

```bash
# 启动向量库依赖
docker compose up -d

# 查看服务状态
docker compose ps

# 查看日志（可选）
docker compose logs -f standalone
```

端口说明：

- PostgreSQL：`5432`
- Redis：`6379`
- Milvus：`19530`
- Milvus 健康检查：`9091`
- MinIO API：`9000`
- MinIO Console：`9001`
- Attu：`8080`

### 3) 使用 pyproject 安装依赖

在项目根目录执行：

```bash
# 方式 A：推荐（uv）
uv sync

# 方式 B：pip
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

## 创建 `.env` 文件

```bash
cp .env.example .env
```

按需编辑 `.env` 中的 API Key、模型名与连接地址；变量说明见 `.env.example` 内注释。

## 运行

### 前端

```bash
cd frontend

# 安装前端依赖
npm install

# 每次启动服务都执行（开发模式）
npm run dev

# 或

# 只执行一次（因为后端接管了前端）
npm run build
```

### 后端（2种方式：uv/pip）

#### 方式 A：推荐（uv）

```bash
# 运行服务
uv run python backend/app.py

# 或

uv run uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

#### 方式 B：pip

```bash
# 进入虚拟环境
# Windows CMD 方式：
.venv\Scripts\activate

# Windows PowerShell 方式：
.venv\Scripts\activate.ps1

# Linux/macOS 方式：
source .venv/bin/activate

# 运行服务
python backend/app.py

# 或

uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

## 浏览器访问

1）如果运行了`npm run build`：

- 可直接访问后端：`http://127.0.0.1:8000/` （后端静态托管了编译后的 `frontend/dist` 资源）
- API 文档：`http://127.0.0.1:8000/docs`

2）如果只运行`npm run dev`：

- 需访问前端页面：`http://127.0.0.1:3000/`

## 项目概览

- **核心能力**：
  - LangChain Agent + 自定义工具。
  - 文档上传后执行三级滑动窗口分块，叶子分块向量化写入 Milvus，父级分块写入 PostgreSQL。
  - 用户注册/登录、JWT 鉴权、基于角色的 RBAC 权限控制（admin/user）。
  - 会话记忆与摘要，聊天与历史记录落地 PostgreSQL，并引入 Redis 缓存热点会话与父文档。
- **运行形态**：FastAPI 后端 + 现代工程化前端（Vite + Vue 3 + TypeScript + Pinia）+ Milvus 向量库。

## 关键创新点

- **混合检索落地**：稠密向量 + BM25 稀疏向量，Milvus Hybrid Search + RRF 排序，兼顾语义与词匹配。
- **自适应问题分解与并行 Sub-Agent 图流程**：主图利用 LLM 分类器自动研判提问复杂度。简单问题直接检索；复杂问题通过 LLM 拆解为 2-4 个独立子问题，利用 LangGraph 的 `Send` API 并行启动子 Agent 完整流程，最终在 Synthesis 节点进行去重合成，解决多跳跨域召回痛点。
- **纠错型 RAG（Corrective RAG）与多策略自适应重写**：检索后引入结构化评分器，判断文档与问题的相关性（Yes/No）。当评分过低或无结果时，智能重写路由在退步问题扩展（`step_back`）、假设性文档生成（`hyde`）和综合扩展（`complex`）间自适应选择，实施二次重度扩展检索。
- **Jina Rerank 接入**：Hybrid/Dense 召回后进行 API 级精排，支持返回 `rerank_score` 并在前端可视化。
- **双向降级**：稀疏生成或 Hybrid 调用失败时自动降级为纯稠密检索，提升稳定性。
- **流式输出（Streaming）**：后端基于 `agent.astream(stream_mode="messages")` 逐 token 推送，前端 SSE + ReadableStream 实现打字机效果。
- **实时 RAG 过程可视化**：检索过程在模型"思考中"阶段就开始展示，通过 `asyncio.Queue` + 后台任务架构实现工具执行期间的实时推送。
- **工具调用过程可视化**：捕获 Agent 的 `tool_call_chunks`，发射 `tool_call` 事件，思考阶段实时展示"🔧 调用工具：xxx"，回答完成后以可折叠"工具调用（N）"持久展示，与"检索过程"并列。
- **回答终止功能**：前端 `AbortController` + 后端 `StreamingResponse` 支持用户随时中断正在生成的回答。
- **会话摘要记忆**：自动摘要旧消息并注入系统提示，维持上下文且控制 token。
- **文档处理链路**：上传 → 切分 → 稠密/稀疏向量同步生成 → Milvus 入库，支持重复上传自动清理旧 chunk。
- **Milvus 2.5+ 原生 BM25 混合检索**：彻底摒弃本地客户端手写 BM25 序列化和统计同步的繁琐设计。通过在 Milvus 集合 schema 中为 `text` 字段绑定 `FunctionType.BM25` 计算函数，由向量数据库在服务端原生提取稀疏特征，保证高效率的 Dense + Sparse 混合检索与完美的统计对齐。
- **三级分块 + Auto-merging**：L1/L2/L3 三层滑窗切分；检索时优先召回 L3，满足阈值后自动合并到父块（L3->L2->L1）。
- **Leaf-only 向量化存储**：仅叶子分块写入 Milvus，父块写入 DocStore，减少向量冗余并保留上下文聚合能力。
- **工具可扩展**：天气查询示例 + 知识库检索 + 网络搜索（Firecrawl v2 / Serper / DuckDuckGo 多后端可切换），便于按需增添第三方 API 或企业数据源。
- **RAG 过程可观测**：记录检索、评分、重写与来源信息，前端可展开查看每一步细节。
- **查询重写体系**：Step-Back 与 HyDE 两种扩展方式 + 路由选择，必要时触发重写检索。
- **相关性评分门控**：基于结构化输出的 `grade_documents` 判断是否需要重写检索。
- **实时思考链路展示**：通过 `asyncio` 事件循环穿透技术，实现 Agent 在执行 RAG、评分、重写等同步工具时，实时向前端推送思考步骤（Searching -> Grading -> Rewriting），彻底解决"静默思考"问题。

## 未来迭代（Todo Lists）

### RAG部分

#### 数据层、Chunk分块

1. 先做文档结构解析，按文档结构做粗拆分，再用递归字符分块兜底，保证打的主题单元不被拆分（2000-3000token）；再用语义分块做精细化拆分，控制单块大小（512-1024token）
2. 代码块、表格、图片特殊处理
3. 实现 ParentDocument/Auto-merging Retriever 策略 --done

#### 召回层

1. BM25的k1和b新增参数扫描
2. RRF额外做BM25和dense的权重，可以通过AB test确定
3. 做一个小型标注集比较dense only、sparse only、hybrid、hybrid + rerank的gold chunk

#### 生成层

1. 子问题分解（CoT、专门的分解小模型、判断分几个子问题） --done
2. 多文档Refine（一次拼接、串行Refine）
3. 多文档冲突处理（A文档说X，B文档说非X），回答中显式输出“来源存在冲突”

#### 其他

1. 向量嵌入：新增多模态 embedding 能力
2. 搭建 RAG 评估体系
3. Rerank 策略评估（top_k、candidate_k、召回/精排比例）

### 其他能力拓展

1. 开发 SQL assistant Skill
2. 实现暂停功能与人工介入机制 --done
3. 新增问题类型判断，简单问题跳过复杂处理流程 --done
4. 扩展网络搜索能力 --done
5. 支持多步骤规划与任务并行执行 --done
6. 搭建路由器节点，由 LLM 自主判断下一步动作 --done
7. 优化 memory 管理：集成 MemO、LangMem 等方案
8. multi-agent：工具过多，把工具拆分给职责明确的专业化agent，提升工具选择的准确性和整体稳定性
9. 历史记录会话名称可修改 --done
10. 死循环检测与恢复：\_is_stuck + attempt_loop_recovery

## 目录与架构

- 后端：`backend/`（分层包结构，统一 `from backend.xxx import`）
  - [app.py](backend/app.py)：FastAPI 入口、CORS、静态资源挂载。
  - `api/`：HTTP 层
    - [router.py](backend/api/router.py)：路由聚合。
    - `routes/`：`auth`、`sessions`、`chat`、`documents` 分文件。
    - [resources.py](backend/api/resources.py)：Milvus / 上传目录等共享资源。
  - `chat/`：对话域
    - [service.py](backend/chat/service.py)：非流式 / 流式聊天入口。
    - [runtime.py](backend/chat/runtime.py)：模型客户端与每请求 Agent 创建。
    - [request_context.py](backend/chat/request_context.py)：每请求 RAG step、RAG trace、工具预算上下文。
    - [storage.py](backend/chat/storage.py)：会话 PostgreSQL + Redis。
  - `rag/`：检索增强
    - [pipeline.py](backend/rag/pipeline.py)：LangGraph RAG 工作流。
    - [utils.py](backend/rag/utils.py)：混合检索、Rerank、Auto-merging。
  - `indexing/`：文档入库与向量
    - [embedding.py](backend/indexing/embedding.py)：稠密 + BM25 稀疏向量。
    - [document_loader.py](backend/indexing/document_loader.py)：PDF/Word/Excel 分块。
    - [milvus_client.py](backend/indexing/milvus_client.py)、[milvus_writer.py](backend/indexing/milvus_writer.py)。
    - [parent_chunk_store.py](backend/indexing/parent_chunk_store.py)：父级分块 DocStore。
  - `tools/`：LangChain Agent 可调用的 `@tool`（天气、知识库检索）。
    - `mcp/`：[MCP 协议](https://modelcontextprotocol.io)客户端 + 服务端双向适配。
      - [adapters.py](backend/tools/mcp/adapters.py)：把现有 `@tool` 函数转为符合 MCP 协议的 `(name, callable, input_schema)` 三元组。
      - [server.py](backend/tools/mcp/server.py)：用 `MCPServer` / `FastMCP` 把 7 个纯函数工具暴露为 stdio MCP Server,可被 Claude Desktop 等客户端调用。
      - [client.py](backend/tools/mcp/client.py)：读取 `mcp_config.json`,通过 stdio 连接外部 MCP Server 并把工具注入 Agent。
  - `infra/`：[database.py](backend/infra/database.py)、[cache.py](backend/infra/cache.py)、[auth.py](backend/infra/auth.py)。
  - `db/`：[models.py](backend/db/models.py)：ORM 模型。
  - `schemas/`：Pydantic 请求/响应（auth / chat / documents）。
  - `jobs/`：[upload_jobs.py](backend/jobs/upload_jobs.py)：异步上传/删除任务进度。
- 前端：`frontend/`
  - 采用现代工程化设计（Vite + Vue 3 + TypeScript + Pinia + Axios + Sass）。
  - **前端工程架构与状态流**：
    - **Pinia 状态存储**：
      - `stores/auth.ts`：处理 JWT 鉴权状态、用户注册与登录，维持 Bearer 鉴权请求。
      - `stores/sessions.ts`：负责多会话历史的创建、异步载入、删除与切换。
      - `stores/chat.ts`：缓存消息流，承载 RAG 各个阶段执行步骤的响应式更新。
      - `stores/documents.ts`：实现知识库文档的展示并配合接口轮询监听上传异步任务进度。
    - **精细化组件设计**：
      - `ThinkingTrace.vue` & `RetrievalTraceDetails.vue`：动态渲染子/主 Agent 思考状态（Searching, Grading, Rewriting 等步骤），支持展示每路子问题的合并与召回详情。
      - `ToolCallTrace.vue`：与"检索过程"并列展示 Agent 的"工具调用-工具名"过程，思考阶段在 `ThinkingTrace.vue` 实时呈现，回答完成后以可折叠列表持久展示。
      - `References.vue`：折叠卡片展示知识库来源信息，含 RRF Rank、Rerank 语义得分、合并叶子块数、所处层级和页码。
      - `UploadSection.vue` & `DocumentSettings.vue`：管理员控制面板，动态轮询监听并步进展示上传的多阶段状态机进度。
    - **流式解包与主动终止**：
      - `utils/api.ts`：底层采用 `fetch` API 的 `response.body.getReader()` 流式逐块（chunk）解包 SSE 数据，并配合 `AbortController` 绑定终止按钮实现前端主动切断长连接。
  - 在 `frontend/` 目录下运行 `npm run dev` 即可开始开发联调（运行于 <http://localhost:3000）。>
  - 在 `frontend/` 目录下运行 `npm run build` 会生成生产环境编译产物输出至 `frontend/dist/`，供 FastAPI 后端无缝进行静态托管。
- 数据：`data/`
  - `documents/`：上传文档原文件。
- 向量库：Milvus（可由 `docker-compose` 或自建服务提供）。

## 核心流程

### 1) 项目全链路（端到端）

1. 用户在前端输入问题，调用 `POST /chat/stream`（流式）。
2. FastAPI `api/routes/chat.py` 返回 `StreamingResponse(media_type="text/event-stream")`。
3. LangChain Agent 根据问题类型决定是否调用工具：

- 天气问题 → `get_current_weather`
- 知识问答 → `search_knowledge_base`

1. 若命中知识库工具，进入 `rag_pipeline.py` 执行检索工作流，各阶段通过 `ChatRequestContext` 实时推送到前端。
2. 检索结果与 RAG Trace 一起返回，Agent 流式生成最终回答（逐 token 推送）。
3. 前端 ReadableStream 逐块解析 SSE，打字机效果实时渲染。
4. 同时消息持久化到 PostgreSQL，并通过 Redis 缓存加速历史会话回放。

### 2) RAG 全链路（重点）

1. **初次召回**：`retrieve_initial`

- 调用 `retrieve_documents`。
- 先按 `chunk_level == 3` 执行 Milvus Hybrid 检索（Dense + Sparse + RRF），候选池大小由 `RETRIEVAL_CANDIDATE_K` 或 `RETRIEVAL_CANDIDATE_MULTIPLIER` 决定。
- 在完整候选上对叶子块执行 Auto-merging（L3→L2→L1），父块从 DocStore 读取。
- 对合并后的片段走 Jina Rerank 精排并截断 `top_k`（流水线：`recall_merge_rerank`）。

1. **相关性打分门控**：`grade_documents`

- 使用结构化输出打分 `yes/no`。
- `yes` 直接进入生成回答；`no` 进入重写阶段。

1. **查询重写路由**：`rewrite_question`

- 在 `step_back / hyde / complex` 中选择策略。
- 生成 `rewrite_query`、`step_back_question`、`hypothetical_doc` 等中间结果。

1. **二次召回**：`retrieve_expanded`

- 对重写后的查询（或 HyDE 文档）再次检索。
- 同样执行 L3 召回 → Auto-merging → Rerank；多路结果按 `chunk_id` 去重（保留更高分）后返回上下文。

1. **答案生成**：Agent 结合上下文生成最终回答。
2. **可观测追踪**：返回 `rag_trace`，包括

- 评分结果与路由决策
- 重写策略与重写内容
- 初次/二次检索结果
- 三级检索与合并信息（`leaf_retrieve_level`、`auto_merge_*`）
- 检索分数 `score` 与精排分数 `rerank_score`

### 3) 文档入库链路

1. 前端上传 PDF/Word 到 `POST /documents/upload`。
2. 若同名文件已存在：先清除旧向量与父块 PostgreSQL 数据库及 Redis 缓存，保障库内状态一致。
3. `document_loader.py` 执行三级滑动窗口分块并写入层级元数据（chunk_id / parent_chunk_id / root_chunk_id / chunk_level）。
4. L1/L2 父级分块写入 `parent_chunk_store.py`（DocStore / PostgreSQL）。
5. L3 叶子分块通过 `milvus_writer` 注入密集向量（由本地 `embedding.py` 的 `HuggingFaceEmbeddings` 产生），并将原始文本写入配置了原生分词中文分析器的 `text` 字段。
6. Milvus 在数据库端自动、同步触发原生 BM25 逆向抽取，动态生成并存储稀疏向量至 `sparse_embedding`，无需客户端介入统计。
7. 后续检索可直接利用新文档参与召回。

### 4) Milvus 2.5+ 原生 BM25 处理

- **机制**：项目利用了 Milvus 2.5+ 新版内置的全文检索机制。创建集合时，定义一个 `FunctionType.BM25` 类型的函数，输入字段为 `text` 字段，输出字段为 `sparse_embedding`。
- **自动对齐**：当新文本 chunk 插入或删除时，Milvus 在服务端自动进行分词、统计、稀疏特征向量计算。这实现了高效率、零客户端统计负担的密集 + 稀疏混合双塔检索。

### 5) 会话记忆链路

1. 每轮问答按当前登录用户 + `session_id` 写入 PostgreSQL。
2. 当消息过长时触发摘要压缩，保留长期上下文。
3. Redis 缓存会话列表与会话消息，减少高频读取数据库压力。
4. 前端可通过会话接口读取、删除当前用户自己的历史对话。

## 技术栈

- 后端：FastAPI、LangChain Agents、Pydantic、Uvicorn、SQLAlchemy、PostgreSQL、Redis。
- 向量与检索：Milvus（HNSW 稠密索引 + SPARSE_INVERTED_INDEX 稀疏索引）、RRF 融合、Jina Rerank 精排。
- 嵌入与稀疏：`langchain_huggingface` 本地稠密向量（默认 `BAAI/bge-m3`）；Milvus 2.5+ 原生 Chinese 分析器与原生 BM25 特征提取。
- 前端：Vite + Vue 3 (SFC) + TypeScript + Pinia + Axios + Marked + Highlight.js + FontAwesome，工程化编译与静态文件托管。
- 工具链：dotenv 配置、requests、langchain_text_splitters、langchain_community.loaders。

## 环境变量

需在仓库根目录或运行环境配置：

- 模型相关：`ARK_API_KEY`、`MODEL`、`BASE_URL`
- 稠密向量：`EMBEDDING_MODEL`、`EMBEDDING_DEVICE`、`DENSE_EMBEDDING_DIM`（需与 Milvus 集合 `dense_embedding` 维度一致）、`HF_ENDPOINT`（HuggingFace 镜像源）、`HF_HUB_OFFLINE`（默认 `1`，模型已下载后跳过联网检查避免启动卡死；设为 `0` 可下载新模型）
- 密集与稀疏：由 Milvus 原生支持的内部分词与 BM25 函数自动处理，无需手动配置客户端 `BM25_STATE_PATH`
- Rerank 相关：`RERANK_MODEL`、`RERANK_BINDING_HOST`、`RERANK_API_KEY`
- Milvus：`MILVUS_HOST`、`MILVUS_PORT`、`MILVUS_COLLECTION`
- 数据库缓存：`DATABASE_URL`、`REDIS_URL`
- 鉴权相关：`JWT_SECRET_KEY`、`ADMIN_INVITE_CODE`、`JWT_ALGORITHM`、`JWT_EXPIRE_MINUTES`
- 密码参数：`PASSWORD_PBKDF2_ROUNDS`
- 检索候选池：`RETRIEVAL_CANDIDATE_K`（固定候选数，优先）、`RETRIEVAL_CANDIDATE_MULTIPLIER`（未设 K 时 `max(top_k × 倍数, top_k)`，默认 `3`）
- Auto-merging：`AUTO_MERGE_ENABLED`、`AUTO_MERGE_THRESHOLD`、`LEAF_RETRIEVE_LEVEL`
- 工具：天气查询优先使用 [uapis.cn](https://uapis.cn) 公共接口，失败时自动切换 Open-Meteo 备用源（均免费、无需配置）；网络搜索 `WEB_SEARCH_API`（默认 `firecrawl`，可选 `serper` / `duckduckgo`）、`FIRECRAWL_API_KEY`、`SERPER_API_KEY`
- MCP：`NOVACHAT_MCP_ENABLED`（默认 `1` 开启;设为 `0` 关闭外部 MCP Server 工具加载）
- 聊天附件：`CHAT_VISION_ENABLED`（默认 `0`）。为 `0` 时只允许上传文档（pdf/doc/docx/txt/md/xls/xlsx），图片会被明确拒绝；所用模型支持图像理解时设为 `1`，图片会按多模态消息发给模型

## MCP 工具协议支持

NovaChat 在 `backend/tools/mcp/` 下提供 **MCP(Model Context Protocol)** 双向支持:

### 服务端:把本地工具暴露为 MCP Server

7 个纯函数工具(`get_current_weather` / `list_documents` / `get_current_time` / `calculate` / `web_search` / `analyze_text`)会被注册到一个 stdio MCP Server,可供 Claude Desktop、Cursor 或任意 MCP 客户端调用。

> 注:截至本文档,实际注册为 6 个。原因见下。

```bash
# 启动本地 MCP Server (stdio)
python -m backend.tools.mcp.server
```

> `search_knowledge_base` 依赖每请求的 `ChatRequestContext`,不在此处暴露(子进程无法访问主进程上下文)。
>
> `analyze_conversation_history`(会话历史分析)同样依赖每请求的 `ChatRequestContext`:其分析范围**严格限定在当前会话内**,以 `session_id` 为唯一作用域,禁止跨会话检索或关联其他会话数据,因此也不在此处暴露。
>
> Agent 会优先使用 MCP Server 提供的同名工具，同时保留本地实现作为降级路径；MCP 子进程启动失败时，天气、时间、搜索和计算等能力仍可继续使用。

### 客户端:接入外部 MCP Server

复制 [mcp_config.example.json](mcp_config.example.json) 为 `mcp_config.json`,声明要接入的外部 MCP Server:

```bash
cp mcp_config.example.json mcp_config.json
# 编辑 mcp_config.json,填入 npx 命令、参数、env 等
```

配置格式兼容 Claude Desktop；本地 NovaChat 工具建议使用当前后端解释器启动：

```json
{
  "mcpServers": {
    "novachat-local": {
      "command": "${PYTHON}",
      "args": ["-m", "backend.tools.mcp.server"],
      "cwd": "${PROJECT_ROOT}"
    }
  }
}
```

`${PYTHON}` 会解析为当前运行后端的 Python（包括 `.venv`），`${PROJECT_ROOT}` 会解析为项目根目录。NovaChat 还会让本地 MCP 子进程继承 API Key 等运行环境，并强制使用 UTF-8 stdio，避免搜索结果包含中文时协议响应失败。

启动后端时,`backend/chat/runtime.py` 会自动通过 stdio 拉起所有配置的外部 Server，并按工具名覆盖对应的本地实现。失败的 Server 会被跳过并记录警告，Agent 将继续使用本地工具，不影响天气、时间、搜索和计算等基础能力。

### 验证测试

```bash
.venv\Scripts\python.exe tests\test_mcp.py
```

测试覆盖:工具适配、配置解析、Server 注册、环境变量开关 4 个用例。

## API 速览

- 鉴权
  - `POST /auth/register`：注册（支持普通用户/管理员邀请码模式）。
  - `POST /auth/login`：登录，返回 Bearer Token。
  - `GET /auth/me`：获取当前登录用户信息。
- 聊天
  - `POST /chat`：聊天（非流式），入参 `message`、`session_id`、可选 `attachments:[{id}]`。
  - `POST /chat/stream`：聊天（流式 SSE），入参同上，返回 `text/event-stream`。
  - `GET /chat/capabilities`：返回 `{vision_enabled}`，前端据此决定附件选择器是否接受图片。
  - `POST /chat/attachments`：上传聊天附件（`multipart/form-data`），返回附件 `id`/`filename`/`kind` 等元数据。
  - `GET /chat/attachments/{id}/file`：取回自己上传的附件原始文件（图片气泡与下载走该接口，需 Bearer Token）。
- 会话（用户隔离）
  - `GET /sessions`：列出当前用户会话。
  - `GET /sessions/{session_id}`：拉取当前用户某会话消息。
  - `DELETE /sessions/{session_id}`：删除当前用户会话。
- 文档（管理员权限）
  - `GET /documents`：列出已入库文档及 chunk 数。
  - `POST /documents/upload`：上传并向量化 PDF/Word/Excel。
  - `DELETE /documents/{filename}`：删除指定文档向量数据（会先按文件名分页拉取 chunk 文本并同步扣减 BM25 持久化统计，再删 Milvus）。

## 流式输出与实时检索过程 — 技术细节

### 1. 跨线程事件调度（Cross-Thread Event Scheduling）

这是一个解决 **"同步工具阻塞异步事件循环"** 问题的关键架构设计，常用于 Python 异步 Web 服务与 CPU 密集型/IO 密集型任务的混合场景。

**痛点**：
FastAPI 运行在单线程的 asyncio Event Loop 上。为了不阻塞主线程，LangChain 通常将同步工具（如 `search_knowledge_base`）放到 `ThreadPoolExecutor` 中运行。但在子线程中，无法直接访问主线程的 `asyncio.Queue`，且 `asyncio.get_event_loop()` 通常会失败。

**解决方案**：
我们采用了 **"Request Context + Threadsafe Callback"** 模式：

1. **请求上下文创建 (Service Layer)**:
   `chat_with_agent_stream()` 为每个请求创建独立的 `ChatRequestContext`，其中保存本请求的 `output_queue` 与主事件循环。
2. **显式依赖注入 (Tool/RAG Layer)**:
   运行时使用 `create_agent_for_request(ctx)` 为本请求创建 agent，并通过 `make_search_knowledge_base(ctx)` 创建捕获该 `ctx` 的专属工具。RAG pipeline 入口为 `run_rag_graph(question, ctx)`。
3. **跨线程发射 (Worker Thread)**:
   RAG 节点调用 `ctx.emit_rag_step(...)`，内部使用本请求保存的 `loop.call_soon_threadsafe(queue.put_nowait, event)` 将事件投递回主 Loop。
4. **隔离保证**:
   RAG step、RAG trace、知识库工具调用计数都存放在请求上下文对象中。

```python
# 核心代码摘要
ctx = ChatRequestContext.for_stream(
    user_id=user_id,
    session_id=session_id,
    output_queue=output_queue,
)
agent = create_agent_for_request(ctx)

# RAG 节点内
ctx.emit_rag_step("🔍", "正在检索知识库...", "初始检索")
```

### 2. 混合检索（Hybrid Search）深度实现

项目并非在客户端手写复杂的 BM25 特征序列化，而是利用 Milvus 2.5+ 服务端原生分析器构建了极致的双塔检索：

- **Dense Pathway**：使用 `langchain_huggingface.HuggingFaceEmbeddings`（默认 `BAAI/bge-m3`）生成稠密向量，维度由 `DENSE_EMBEDDING_DIM` 与集合 schema 对齐（默认 1024），向量可做 L2 归一化后与 Milvus `IP` 度量配合。
- **Sparse Pathway**：
  - 文档写入时，仅需将原始文本写入启用 `chinese` 分析器分词的 `text` 字段。
  - Milvus 服务端自动运行绑定的 `FunctionType.BM25` 计算函数，动态生成对应的稀疏嵌入并同步到 `sparse_embedding` 索引中，完美对齐词表统计。
- **Milvus 融合**：
  - 使用 Milvus 的 `AnnSearchRequest` 同时发起稠密和稀疏的两个多路检索请求。
  - **RRFRanker (Reciprocal Rank Fusion)**: 采用 `k=60` 的倒数排名融合算法，将两路召回结果无参数化地合并，避免了加权求和中调节 `alpha` 参数的困难。

### 3. 前端 "Thinking State Machine"

前端 `stores/chat.ts` 结合响应式组件 `ThinkingTrace.vue` 维护了一个微型状态机来处理通过 SSE 传回的复杂混合流：

1. **Idle**: 等待用户输入。
2. **Thinking (Initial)**: 收到请求，创建消息气泡并置其 `isThinking=true`。
3. **Thinking (Active RAG)**: 收到 `type: "rag_step"` 事件。
   - 状态机保持 `isThinking=true`。
   - 动态更新当前 RAG 步进文字与状态细节卡片（例如显示 "正在重写查询..."、"Auto-merging 合并完成" 等）。
   - 往消息项的 `ragSteps` 数组追加步骤，实时推送到组件渲染。
4. **Streaming**: 收到首个 `type: "content"` 事件。
   - **立即切换**: 标记并设置 `isThinking=false`。
   - 并不销毁或重建气泡，而是隐藏思考详情头部，开始在同一个气泡内流式追加 Markdown 正文文本。
   - 这样实现了从 "动态检索步骤思考" 到 "大模型流式回答" 的无缝视觉过渡，视觉上极为顺滑。

## 整体架构

```
用户发送消息
    │
    ▼
POST /chat/stream → StreamingResponse(text/event-stream)
    │
    ▼
chat_with_agent_stream()
    │
    ├── 创建统一输出队列 (asyncio.Queue)
    ├── 创建 ChatRequestContext.for_stream(...)
    ├── create_agent_for_request(ctx) 绑定本请求专属 tool
    ├── 启动 _agent_worker 后台任务 (asyncio.create_task)
    │     └── agent.astream(stream_mode="messages") 逐 token 产出
    │           ├── AIMessageChunk (文本) → {"type": "content"} 入队
    │           └── tool_call_chunks (工具调用) → {"type": "tool_call", "tool_name", "call_id"} 入队
    │
    └── 主循环：await output_queue.get() → yield SSE
          ▲
          │ (并发) RAG 工具在线程池中执行
          │ ctx.emit_rag_step() → loop.call_soon_threadsafe → 入队
          │ {"type": "rag_step"} 立即从队列取出并推送到前端
```

### 后端实现

#### 1) 流式生成 (`agent.py`)

- 使用 LangGraph `agent.astream(stream_mode="messages")` 获取逐 token 的 `AIMessageChunk`。
- 捕获 `tool_call_chunks`：当模型决定调用工具时，发射 `{"type": "tool_call", "tool_name", "call_id"}` 事件给前端，按 `call_id`（缺省回退到 `tool_name`）去重，同一调用只发一次；文本内容仍正常转发给前端。
- **关键设计**：Agent 流式循环运行在 `asyncio.create_task` 后台任务中，主生成器只负责从统一 `output_queue` 取事件并 yield。这样 RAG 步骤在工具执行期间（agent 阻塞等待工具返回时）仍然可以实时推送到前端。

#### 2) 实时 RAG 步骤推送 (`tools.py` + `rag_pipeline.py`)

- `ChatRequestContext.emit_rag_step(icon, label, detail)` 通过请求创建时捕获的 `loop.call_soon_threadsafe()` 将步骤从同步线程安全地推送到本请求的异步队列。
- `make_search_knowledge_base(ctx)` 创建本请求专属 tool，LLM 仍只看到 `query` 参数；Python closure 持有当前请求的 `ctx`。
- `rag_pipeline.py` 通过 `run_rag_graph(question, ctx)` 接收上下文，子问题进度使用安全标签（如 `子问题 1`）分组。
- `rag_pipeline.py` 在每个关键节点发射步骤：
  - `retrieve_initial` → "正在检索知识库..."
  - `grade_documents` → "正在评估文档相关性..."
  - `rewrite_question` → "正在重写查询..."（含策略选择）
  - `retrieve_expanded` → "使用扩展查询重新检索..."

#### 3) SSE 协议格式

每个事件格式：`data: {JSON}\n\n`，类型字段：

- `content`：文本 token（打字机效果）
- `rag_step`：实时检索步骤（`{icon, label, detail}`）
- `tool_call`：工具调用过程（`{tool_name, call_id}`），按 `call_id`/`tool_name` 去重，与"检索过程"并列展示
- `trace`：完整 RAG 追踪信息（回答完成后发送）
- `error`：错误信息
- `[DONE]`：流结束标记

#### 4) StreamingResponse 配置 (`api.py`)

```python
StreamingResponse(
    event_generator(),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
    },
)
```

### 前端实现

#### 1) ReadableStream 解析 (`utils/api.ts`)

- 使用 `response.body.getReader()` + `TextDecoder` 逐块读取。
- 手动按 `\n\n` 分割 SSE 事件，解析 `data: ` 前缀后的 JSON。
- `content` 事件追加到消息文本；`rag_step` 事件追加到检索步骤数组并同步更新思考状态文字；`tool_call` 事件追加到消息的 `toolCalls` 数组，并按 `call_id`/`tool_name` 去重。

#### 2) 思考气泡二合一

- 发送消息后立即创建带 `isThinking: true` 的气泡，显示跳动圆点 + 动态文字。
- 收到 `tool_call` 时，在思考气泡内实时展示"🔧 调用工具：xxx"列表（与 RAG 步骤并列、左侧带主色边线）。
- 收到 `rag_step` 时，`thinkingLabel` 更新为当前步骤（如"正在检索知识库..."）。
- 收到第一个 `content` token 时，`isThinking = false`，同一气泡无缝切换为正常文本流。
- **不存在两个分离的气泡**，从思考 → 工具调用 → 检索 → 回答全程在同一个气泡内完成。
- 回答完成后，`ToolCallTrace.vue` 在消息底部以可折叠"工具调用（N）"形式持久展示工具调用过程，与"检索过程"并列。

#### 3) Vue 3 响应式注意事项

- 通过 `this.messages[botMsgIdx]` 索引访问（而非缓存对象引用），确保拿到 Vue 的 reactive proxy。
- `ragSteps` 数组通过 `push()` 触发响应式更新。

### 终止功能

#### 前端

- 发送按钮在 `isLoading` 期间切换为红色终止按钮（`v-if/v-else`）。
- 点击调用 `AbortController.abort()`，取消正在进行的 `fetch` 请求。
- 捕获 `AbortError`，在气泡中显示"(已终止回答)"。

#### 后端

- FastAPI 的 `StreamingResponse` 在客户端断开连接（如浏览器触发 `abort()` 或关闭标签页）时，会检测到 socket 断开。
- Python 的生成器协议会向响应生成器抛出 `GeneratorExit` 异常。
- **实现细节**：采用**主动防御式编程**，显式捕获 `GeneratorExit` 并执行 `agent_task.cancel()`。
- **为什么不依赖框架自动取消？**：虽然 Starlette/FastAPI 拥有基于 `BaseHTTPMiddleware` 的级联取消机制（Cascading Cancellation），但在复杂的后台任务结构或特定中间件配置下，取消信号可能延迟或在传递链中丢失。显式调用 `.cancel()` 提供了**确定性的资源回收**保证。
- **即时止损原理**：`agent_task.cancel()` 会立即在任务挂起点注入 `asyncio.CancelledError`。对于流式 LLM 请求，这会触发 `httpx` 关闭 TCP 连接。服务端（OpenAI 等）检测到 client 掉线后会立即停止推理，从而实现**真正的 Token 节省**。

## 更新日志

### 2026-10-27 用户对话支持「添加图片或文件」

- **附件上传**：`POST /chat/attachments` 保存文件到 `data/chat_uploads/` 并登记到新表 `chat_attachments`。图片限 8MB（png/jpg/jpeg/gif/webp/bmp），文档限 30MB（pdf/doc/docx/txt/md/xls/xlsx），单条消息最多 6 个附件；未发送的附件 24 小时后在启动时自动清理。
- **文档注入**：文档在**上传时**提取纯文本（复用知识库侧的解析链路，`.doc` 走 antiword → LibreOffice → Word COM 降级），发送时以「【附件文档：文件名】+ 正文」注入模型上下文，单文档上限 3 万字、单条消息合计 6 万字，超限截断并明确标注。
- **图片多模态**：使用支持图像理解的模型时设置 `CHAT_VISION_ENABLED=1`，图片会转成 `image_url` 内容块与其他文本一起发给模型；未开启时上传图片直接返回可读错误，而不是把 provider 的原始报错抛给用户。
- **展示与持久化**：用户消息落库保留纯文本内容，附件元数据（`id`/`filename`/`kind`/`mime`）存入 `chat_messages.attachments`；气泡内渲染图片缩略图（点击大图预览）与文档卡片（点击下载），刷新或切换会话后仍然可见。附件按用户隔离，取文件需 Bearer Token。
- **其它**：前端附件在上传阶段完成（带进度与失败提示），支持从剪贴板粘贴图片；`chat_messages` 采用「删后重插」写库，现按下标继承历史消息的 `rag_trace`/附件元数据，避免开新一轮时清空历史展示数据。

### 2026-08-24 修复后端启动卡死导致首页持续转圈

- **根因**：`backend/indexing/embedding.py` 在模块导入时实例化 `HuggingFaceEmbeddings`，其内部会联网检查模型更新。当 `HF_ENDPOINT` 指向的镜像站（`hf-mirror.com`）连接超时或不可达时，整个后端启动流程被阻塞，FastAPI 无法处理 HTTP 请求，表现为 `http://localhost:8000/` 一直转圈。
- **修复**：在 [backend/env.py](backend/env.py) 的 `load_env()` 中，当用户未显式设置 `HF_HUB_OFFLINE` 时默认置为 `1`，使 `huggingface_hub` 走离线模式直接使用本地缓存。模型已下载到本地后无需每次启动联网校验，启动耗时从"无限卡死"降至正常水平。
- **可配置**：如需下载新模型，在 `.env` 中设置 `HF_HUB_OFFLINE=0` 或临时注释该行即可恢复联网。

### 2026-08-23 网页搜索结果展示带 🔗 超链接标识

- **工具输出格式**：`web_search` 工具返回结果中每条记录改为 markdown 链接格式 `[标题](链接)`，便于大模型在最终回答里直接引用与保留链接。
- **行内引用规则**：在 `SYSTEM_PROMPT` 中新增规则，要求模型基于 `web_search` 结果回答时，超链接就近放在正文对应陈述句后面（而非末尾统一列出「来源：」段落）。
- **前端统一标识**：`main.css` 给 `.message-content` 内所有 `<a>` 标签自动添加 `🔗 ` 前缀（代码块 `<pre>` / `<code>` 内除外），用户可通过 🔗 符号一眼识别网页搜索来源链接。

### 2026-08-23 网络搜索工具接入 Firecrawl v2 并支持自定义返回条数

- **Firecrawl v2 后端**：网络搜索工具默认改用 Firecrawl v2 搜索接口（`https://api.firecrawl.dev/v2/search`），结果质量与稳定性优于原 DuckDuckGo。原 `serper` / `duckduckgo` 后端保留，可通过 `WEB_SEARCH_API` 环境变量切换。
- **智能返回条数**：`web_search` 工具新增 `num_results` 参数，大模型可根据用户提示词中指定的条数（如"搜索 3 条"、"返回前 8 条"）自动设置；未指定时默认返回 5 条，上限 10 条。工具描述中已显式引导模型解析用户意图。
- **配置变更**：`.env.example` 新增 `FIRECRAWL_API_KEY`，`WEB_SEARCH_API` 默认值由 `duckduckgo` 改为 `firecrawl`。

### 2026-08-16 新增站点备案信息与 GitHub 仓库入口

- **ICP 备案链接**：在登录页底部与聊天页输入区 footer 新增备案号链接（赣ICP备2026017220号），指向工信部备案查询站点 `https://beian.miit.gov.cn/`。
- **GitHub 仓库入口**：聊天页 header 新增 GitHub 图标按钮，登录页 intro 区新增 GitHub 仓库胶囊链接，均指向 `https://github.com/amd47802574/NovaChat`。

### 2026-06-12 全面迁移至 Milvus 2.5+ 原生 BM25 与事务级可靠删除

- **服务端原生 BM25**：重构并迁移至 Milvus 2.5+ 内置中文分词器与 BM25 Pipeline 函数。完全移除客户端的手写分词、稀疏特征向量计算及 `bm25_state.json` 状态文件，极大降低客户端负担。
- **Schema 自动升级**：优化 `ensure_collection` 逻辑，支持自动检测旧版 Schema 并进行 drop 与无缝重建升级。
- **事务性一键删除**：实现高可靠、强一致性的 `delete_document_transactionally` 删除协调器，一键清理 Milvus 向量数据、PostgreSQL 级联分块记录和 Redis 热缓存，避免产生任何悬空脏数据。
- **企业级文本净化**：升级文本清洗逻辑，通过 Unicode NFC 标准规范化和 PUA/C0/C1 等非打印/零宽/孤立代理项的彻底过滤，解决 PostgreSQL 与 Milvus 的字符集兼容性报错。

### 2026-06-12 前端单文件 CDN 重构为 Vite + Vue 3 + TS 工程化组件架构

- **现代化架构重构**：将以前臃肿的多合一 HTML/CDN 页面重构为标准的 **Vite + Vue 3 (SFC) + TypeScript + Pinia + Axios + Sass** 现代化工程项目，全部组件和状态高度解耦。
- **状态及路由管理**：利用 Pinia 建立了 `auth`、`sessions`、`chat`、`documents` 四大 Store 共享核心数据。
- **高阶交互界面**：增加流式上传进度详情卡片、上传成功后卡片自动折叠、References 参考文献精美折叠展示、Thinking 气泡流畅过度等。

### 2026-06-03 自适应复杂问题分解、并行 Sub-Agent 与精排门控

- **提问复杂度分类**：内置 LLM 分类路由，简单问题直发检索，复杂问题通过 LLM 拆解为 2-4 个高覆盖、互不重叠的独立子问题。
- **并行子 Agent 推理**：利用 LangGraph 的 `Send` API 并行发起到独立的子图流程（`rag_sub_agent`），使每个子问题分别执行完整的 retrieve、grade、rewrite 判定。
- **子步骤完美分组**：前端界面重新适配并行子流程，在 RAG Step 的 SSE 数据中为子问题建立独立分组标签展示，避免交错重复建组与视觉混淆。
- **精排阈值与 Step-back 强制路由**：加入 `RERANK_MIN_SCORE` 准入门槛过滤噪音。当精排过滤后结果为空时，强制执行 step-back 扩展重写，保证长尾问题的基本召回兜底。

### 2026-06-02 通用 RAG 能力强化与后端生命周期重构

- **通用 RAG 功能增强**：新增思考模式切换、会话摘要长期记忆（Context Manager Notes）、智能会话标题自主生成，以及多源参考文献的可视化折叠展示卡片。
- **gRPC 连接生命周期优化**：Milvus 数据库客户端访问由全局连接池改为短生命周期会话（`session()` contextmanager），按请求建立短连接会话，彻底规避连接因长期挂起产生的失效 gRPC channel 问题。
- **后端分层重组与包依赖解耦**：彻底重构 backend 代码目录包结构，剔除 re-export 导出机制，解决因交叉导入产生的循环依赖，并统一环境加载规范。

### 2026-06-01 召回-合并-精排（Rerank）流水线重构

- **模块化 Pipeline**：重构 RAG 底层实现，将 RAG 流程收拢为高可控的“召回 -> 自动合并 -> 语义重排”流水线，收口统一的参数配置与多级 RAG Trace 追踪。
- **去重合并高分保留**：修复了在执行 L3 -> L2/L1 叶子向上合并时，在循环内聚合 Rank 分数的算法，防止去重过程中丢失高置信度召回分。

### 2026-04-08 本地嵌入与 BM25 持久化

- **稠密向量**：由兼容 API 改为 `langchain_huggingface` 本地模型（默认 `BAAI/bge-m3`），支持 `EMBEDDING_MODEL` / `EMBEDDING_DEVICE`；Milvus `dense_embedding` 维度与 `DENSE_EMBEDDING_DIM` 对齐（默认 1024）。
- **BM25 统计**：`词表 vocab + 文档频次 doc_freq + 文档数 N` 持久化至 `data/bm25_state.json`（可选 `BM25_STATE_PATH`）；每个叶子 chunk 视为一篇文档，入库时 **increment_add**，删除文档或覆盖上传前按文件名从 Milvus 拉取 chunk 文本后 **increment_remove**；`embedding_service` 在 `api` 与 `rag_utils` 间单例共享，避免写入与检索状态分裂。
- **Milvus 查询**：单次 `query` 的 `limit` 受服务端窗口限制（如 16384），新增 **`query_all`** 分页拉取，供删除/覆盖前取回全文以同步 BM25；修复单次 `limit=100000` 导致的 RPC 报错。
- **说明**：README「环境变量」「文档入库」「混合检索」「数据目录」等已同步为上述行为；`data/` 下 `bm25_state.json` 通常被 git 忽略，空库仅有 Milvus 无状态文件时需自行重建或重导。

### 2026-03-21 后端服务建设升级（认证 + 数据库 + 缓存）

- 新增认证与权限模块：注册、登录、JWT、管理员权限控制。
- 聊天历史从本地 JSON 迁移到 PostgreSQL，按用户隔离会话数据。
- 父级分块存储从本地 JSON 迁移到 PostgreSQL。
- 引入 Redis 缓存会话与父文档，提高读取性能并降低数据库压力。
- API 升级为 Token 驱动，移除前端直接传 `user_id` 的历史模式。
- 文档管理接口收敛到管理员角色，避免普通用户误操作知识库。
- 密码哈希方案升级为 PBKDF2-SHA256，兼容历史 bcrypt 校验。

### 2026-03-13 三级分块与 Auto-merging 升级

- 新增三级滑动窗口分块（L1/L2/L3），并为分块写入层级元数据。
- 存储策略调整为 Leaf-only：仅 L3 叶子块写入 Milvus，L1/L2 写入本地 DocStore。
- Auto-merging 改为从 DocStore 拉取父块，减少向量冗余存储。
- 思考链路新增三级检索与自动合并步骤事件。
- `rag_trace` 新增 `leaf_retrieve_level` 与 `auto_merge_*` 字段，且历史会话读取同样保留这些字段。

### 2026-02-19 RAG 实时思考链路修复

- **问题**：Agent 在执行同步工具（如 `search_knowledge_base`）时，由于运行在线程池中，无法正确获取主线程的 asyncio 事件循环，导致 `emit_rag_step` 事件丢失，前端"思考中"气泡一直静止。
- **修复**：
  1. **Backend (`service.py`)**：为每个请求创建 `ChatRequestContext`，在其中捕获主线程 `loop` 与本请求 `output_queue`。
  2. **Backend (`tools.py`** **+** **`rag_pipeline.py`)**：使用 per-request tool factory 与显式 `ctx` 参数跨线程调度 RAG step，避免请求间串号。
  3. **Frontend (`stores/chat.ts`)**：在发送消息时初始化空的 `ragSteps: []` 数组，确保 Vue 响应式系统能立即追踪后续的 push 操作。
- **效果**：用户提问后，思考气泡内实时跳动显示检索步骤（如"🔍 正在检索知识库..." -> "📊 正在评估文档相关性..."），不再只有静态的"正在思考中..."。
