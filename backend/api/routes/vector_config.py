"""超级管理员专属的向量模型配置与迁移接口。"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.db.models import User
from backend.infra.audit import write_audit_log
from backend.infra.auth import get_client_ip, get_db, require_super_admin
from backend.infra.vector_config import (
    _normalized_payload,
    _stored_values,
    apply_rerank_config,
    embedding_config_changed,
    get_migration_job,
    get_vector_config,
    start_migration,
)
from backend.schemas import (
    UpdateVectorConfigRequest,
    UpdateVectorConfigResponse,
    VectorConfigField,
    VectorConfigResponse,
    VectorMigrationJobResponse,
)

router = APIRouter(prefix="/super-admin", tags=["super-admin"])


@router.get("/vector-config", response_model=VectorConfigResponse)
def get_vector_config_route(_: User = Depends(require_super_admin)):
    data = get_vector_config()
    return VectorConfigResponse(
        config=[VectorConfigField(**field) for field in data["config"]],
        migration_running=data["migration_running"],
        applied_at=data["applied_at"],
    )


@router.put("/vector-config", response_model=UpdateVectorConfigResponse)
def update_vector_config_route(
    payload: UpdateVectorConfigRequest,
    http_request: Request,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    data = {key.upper(): value for key, value in payload.model_dump(exclude_unset=True).items()}
    values = _normalized_payload(data, _stored_values())
    try:
        if embedding_config_changed(values, _stored_values()):
            job_id = start_migration(data)
            detail = f"启动向量模型迁移任务 {job_id}，目标模型 {values['EMBEDDING_MODEL']}"
            write_audit_log(
                db=db,
                actor=current_user.username,
                action="vector_model_migration_start",
                target_type="vector_config",
                target_id=job_id,
                detail=detail,
                ip=get_client_ip(http_request),
            )
            return UpdateVectorConfigResponse(
                message="已开始创建新向量集合并重建文档向量；旧集合会保留，完成后自动切换。",
                migration_job_id=job_id,
            )

        apply_rerank_config(data)
        write_audit_log(
            db=db,
            actor=current_user.username,
            action="vector_config_update",
            target_type="vector_config",
            detail=f"更新重排模型配置：{values['RERANK_PROVIDER']} / {values['RERANK_MODEL']}",
            ip=get_client_ip(http_request),
        )
        return UpdateVectorConfigResponse(message="重排模型配置已保存并生效。")
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"保存向量模型配置失败: {exc}") from exc


@router.get("/vector-config/jobs/{job_id}", response_model=VectorMigrationJobResponse)
def get_vector_migration_job_route(
    job_id: str,
    _: User = Depends(require_super_admin),
):
    job = get_migration_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="迁移任务不存在")
    return VectorMigrationJobResponse(**job)
