import asyncio
import logging
import os
import sys
from pathlib import Path

# 支持 `python backend/app.py` 与 `uvicorn backend.app:app` 两种启动方式
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.env import PROJECT_ROOT, load_env

load_env()

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.router import router
from backend.infra.database import init_db

FRONTEND_DIR = PROJECT_ROOT / "frontend" / "dist"
logger = logging.getLogger(__name__)


def _warm_local_embedding_model() -> None:
    try:
        from backend.indexing.embedding import embedding_service

        if embedding_service._config()[0] == "huggingface":
            embedding_service.get_embeddings(["NovaChat 向量检索预热"])
    except Exception as exc:
        logger.debug("本地向量模型预热失败：%s", exc)
        return


def create_app() -> FastAPI:
    app = FastAPI(title="Cute Cat Bot API")

    @app.on_event("startup")
    async def _startup_init_db():
        init_db()
        from backend.tools.mcp.client import load_external_mcp_tools_sync

        app.state.mcp_tools_warmup = asyncio.create_task(
            run_in_threadpool(load_external_mcp_tools_sync)
        )
        app.state.embedding_warmup = asyncio.create_task(
            run_in_threadpool(_warm_local_embedding_model)
        )
        # 清理用户上传后未发送的过期聊天附件，避免磁盘与表记录无限堆积
        from backend.chat.attachments import prune_stale_attachments

        await run_in_threadpool(prune_stale_attachments)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _no_cache(request, call_next):
        response = await call_next(request)
        path = request.url.path or ""
        if path == "/" or path.endswith((".html", ".js", ".css")):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    app.include_router(router)

    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", 8000)))
