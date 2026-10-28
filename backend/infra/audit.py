"""安全审计日志写入助手。

集中处理 audit_logs 表的追加写入，失败仅记录告警而不影响主流程，
避免审计异常拖垮正常的用户管理 / 登录等业务操作。
"""
from sqlalchemy.orm import Session

from backend.db.models import AuditLog


def write_audit_log(
    db: Session,
    actor: str,
    action: str,
    *,
    actor_role: str = "super_admin",
    target_type: str | None = None,
    target_id: str | int | None = None,
    detail: str | None = None,
    ip: str | None = None,
) -> None:
    """追加一条审计记录；任何异常都吞掉并打印告警，保证主流程不中断。"""
    try:
        log = AuditLog(
            actor=actor,
            actor_role=actor_role,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            detail=detail,
            ip=ip,
        )
        db.add(log)
        db.commit()
    except Exception as exc:  # 审计写入失败不应阻断业务
        try:
            db.rollback()
        except Exception:
            pass
        print(f"[audit] 审计日志写入失败（已忽略）: {exc}")
