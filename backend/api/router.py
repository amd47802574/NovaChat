from fastapi import APIRouter

from backend.api.routes.auth import router as auth_router
from backend.api.routes.chat import router as chat_router
from backend.api.routes.documents import router as documents_router
from backend.api.routes.model_config import router as model_config_router
from backend.api.routes.sessions import router as sessions_router
from backend.api.routes.super_admin import router as super_admin_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(sessions_router)
router.include_router(chat_router)
router.include_router(documents_router)
router.include_router(super_admin_router)
router.include_router(model_config_router)
