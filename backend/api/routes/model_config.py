"""模型配置管理接口（超级管理员专属）。

- GET  /super-admin/model-config  ：读取当前模型配置（敏感字段不回显明文）
- PUT  /super-admin/model-config  ：校验、落盘 .env、刷新运行进程内模型单例、记审计

权限：依赖 require_super_admin，普通用户与管理员一律 403。
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.infra.audit import write_audit_log
from backend.infra.auth import get_client_ip, get_db, require_super_admin
from backend.infra.model_config import (
    apply_model_config,
    get_last_applied_at,
    get_model_config,
    save_model_config,
)
from backend.schemas.super_admin import (
    ModelConfigField,
    ModelConfigResponse,
    UpdateModelConfigRequest,
    UpdateModelConfigResponse,
)

router = APIRouter(prefix="/super-admin", tags=["super-admin"])


@router.get("/model-config", response_model=ModelConfigResponse)
def get_model_config_route(_: object = Depends(require_super_admin)):
    try:
        fields = [ModelConfigField(**f) for f in get_model_config()]
        return ModelConfigResponse(
            config=fields,
            applied_at=get_last_applied_at(),
        )
    except Exception as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail=f"读取模型配置失败: {exc}")


@router.put("/model-config", response_model=UpdateModelConfigResponse)
def update_model_config_route(
    payload: UpdateModelConfigRequest,
    http_request: Request,
    current_user: object = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        values = payload.model_dump(exclude_unset=True)
        # 空字符串统一转为 ""（保持「留空沿用」语义，由 save 层判断）
        cleaned = {k: (v if v is not None else "") for k, v in values.items()}

        errors = save_model_config(cleaned)
        if errors:
            from fastapi import HTTPException

            raise HTTPException(status_code=400, detail="; ".join(errors.values()))

        # 写入成功后刷新运行进程内模型单例
        apply_model_config()

        write_audit_log(
            db=db,
            actor=current_user.username,  # type: ignore[attr-defined]
            action="model_config_update",
            target_type="model_config",
            detail="更新并生效模型配置（ARK_API_KEY / BASE_URL / MODEL / GRADE_MODEL / FAST_MODEL）",
            ip=get_client_ip(http_request),
        )

        return UpdateModelConfigResponse(
            message="模型配置已保存并生效",
            applied_at=get_last_applied_at(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail=f"保存模型配置失败: {exc}")
