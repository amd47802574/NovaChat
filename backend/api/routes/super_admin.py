"""超级管理员端 API。

权限边界：
- 所有接口均依赖 `require_super_admin`，普通用户（user）与普通管理员（admin）一律 403，
  与既有管理端（文档管理 require_admin）完全隔离，互不可见、互不可达。
- 全部特权操作（创建/禁用/启用/改角色/登录）都会通过 `write_audit_log` 落审计日志。

访问入口：
- 前端通过侧边栏「超级管理后台」入口（仅 super_admin 可见）进入，URL 以 ?view=sa 标记；
  后端接口统一以 /super-admin 前缀挂载，避免与 /documents 等 admin 接口混淆。
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db.models import AuditLog, ChatMessage, ChatSession, User
from backend.infra.audit import write_audit_log
from backend.infra.auth import get_client_ip, get_db, get_password_hash, require_super_admin
from backend.schemas import (
    AdminUserDetail,
    AdminUserItem,
    AdminUserListResponse,
    AuditLogItem,
    AuditLogResponse,
    CreateUserRequest,
    DashboardMetrics,
    RoleCount,
    ToggleActiveResponse,
    TrendPoint,
    UpdateUserRequest,
    UpdateUserResponse,
)

router = APIRouter(prefix="/super-admin", tags=["super-admin"])


# ------------------------------- 内部辅助 -------------------------------


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _to_admin_item(user: User) -> AdminUserItem:
    return AdminUserItem(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        is_locked=user.is_locked,
        created_at=_iso(user.created_at),
        last_login_at=_iso(user.last_login_at),
        updated_at=_iso(user.updated_at),
    )


def _last_n_days(n: int):
    today = datetime.utcnow().date()
    return [today - timedelta(days=i) for i in range(n - 1, -1, -1)]


def _trend(query_result, days) -> list[TrendPoint]:
    """把 `func.date(col), count` 的结果补齐为连续 n 天的趋势序列。"""
    count_map = {str(d[0]): d[1] for d in query_result}
    return [
        TrendPoint(date=d.isoformat(), count=count_map.get(d.isoformat(), 0))
        for d in days
    ]


# ------------------------------- 数据面板 -------------------------------


@router.get("/metrics", response_model=DashboardMetrics)
def get_metrics(_: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    try:
        total_users = db.query(func.count(User.id)).scalar() or 0
        active_users = (
            db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0
        )
        disabled_users = (
            db.query(func.count(User.id)).filter(User.is_active.is_(False)).scalar() or 0
        )
        admin_users = (
            db.query(func.count(User.id)).filter(User.role == "admin").scalar() or 0
        )
        super_admin_users = (
            db.query(func.count(User.id)).filter(User.role == "super_admin").scalar() or 0
        )
        total_sessions = db.query(func.count(ChatSession.id)).scalar() or 0
        total_messages = db.query(func.count(ChatMessage.id)).scalar() or 0

        # 知识库文档数依赖 Milvus，失败时不阻塞面板，仅记为 0
        total_documents = 0
        try:
            from backend.api.resources import milvus_manager

            milvus_manager.init_collection()
            rows = milvus_manager.query(
                output_fields=["filename"], limit=10000, consistency_level="Strong"
            )
            total_documents = len({r.get("filename") for r in rows})
        except Exception as exc:
            print(f"[metrics] 文档数统计失败（已记为 0）: {exc}")

        days = _last_n_days(7)
        reg_rows = (
            db.query(func.date(User.created_at), func.count(User.id))
            .filter(User.created_at >= days[0])
            .group_by(func.date(User.created_at))
            .all()
        )
        login_rows = (
            db.query(func.date(User.last_login_at), func.count(User.id))
            .filter(User.last_login_at >= days[0])
            .group_by(func.date(User.last_login_at))
            .all()
        )
        role_rows = db.query(User.role, func.count(User.id)).group_by(User.role).all()

        return DashboardMetrics(
            total_users=total_users,
            active_users=active_users,
            disabled_users=disabled_users,
            admin_users=admin_users,
            super_admin_users=super_admin_users,
            total_sessions=total_sessions,
            total_messages=total_messages,
            total_documents=total_documents,
            registrations_last_7_days=_trend(reg_rows, days),
            logins_last_7_days=_trend(login_rows, days),
            role_distribution=[RoleCount(role=r, count=c) for r, c in role_rows],
            generated_at=datetime.utcnow().isoformat(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取面板数据失败: {exc}")


# ------------------------------- 用户管理 -------------------------------


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    _: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        query = db.query(User)
        if q and q.strip():
            query = query.filter(User.username.ilike(f"%{q.strip()}%"))
        total = query.count()
        items = (
            query.order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return AdminUserListResponse(
            users=[_to_admin_item(u) for u in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取用户列表失败: {exc}")


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user(
    user_id: int,
    _: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    item = _to_admin_item(user)
    return AdminUserDetail(
        **item.dict(),
        failed_login_attempts=user.failed_login_attempts or 0,
        locked_until=_iso(user.locked_until),
    )


@router.post("/users", response_model=UpdateUserResponse, status_code=201)
def create_user(
    payload: CreateUserRequest,
    http_request: Request,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    username = (payload.username or "").strip()
    password = (payload.password or "").strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="用户名已存在")

    role = (payload.role or "user").strip().lower()
    if role not in ("user", "admin", "super_admin"):
        raise HTTPException(status_code=400, detail="非法的角色值")
    is_active = True if payload.is_active is None else bool(payload.is_active)

    user = User(
        username=username,
        password_hash=get_password_hash(password),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()

    write_audit_log(
        db,
        actor=current_user.username,
        action="user_create",
        target_type="user",
        target_id=user.id,
        detail=f"创建用户 {username}，角色 {role}，状态 {'启用' if is_active else '禁用'}",
        ip=get_client_ip(http_request),
    )
    return UpdateUserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        message=f"已创建用户 {username}",
    )


@router.put("/users/{user_id}", response_model=UpdateUserResponse)
def update_user(
    user_id: int,
    payload: UpdateUserRequest,
    http_request: Request,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    changes: list[str] = []

    if payload.role is not None:
        new_role = payload.role.strip().lower()
        if new_role not in ("user", "admin", "super_admin"):
            raise HTTPException(status_code=400, detail="非法的角色值")
        # 防御：禁止超级管理员把自己降级，避免后台被锁死
        if user.id == current_user.id and new_role != "super_admin":
            raise HTTPException(status_code=400, detail="不能修改自身的超级管理员角色，避免锁死后台")
        if user.role != new_role:
            old_role = user.role
            user.role = new_role
            changes.append(f"角色 {old_role} → {new_role}")

    if payload.is_active is not None:
        new_active = bool(payload.is_active)
        # 防御：禁止超级管理员禁用自身账号
        if user.id == current_user.id and not new_active:
            raise HTTPException(status_code=400, detail="不能禁用自身账号")
        if user.is_active != new_active:
            user.is_active = new_active
            changes.append("启用" if new_active else "禁用")

    if not changes:
        raise HTTPException(status_code=400, detail="没有需要更新的内容")

    db.commit()
    write_audit_log(
        db,
        actor=current_user.username,
        action="user_update",
        target_type="user",
        target_id=user.id,
        detail=f"用户 {user.username}：" + "；".join(changes),
        ip=get_client_ip(http_request),
    )
    return UpdateUserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        message="用户已更新：" + "；".join(changes),
    )


@router.post("/users/{user_id}/toggle-active", response_model=ToggleActiveResponse)
def toggle_active(
    user_id: int,
    http_request: Request,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能禁用/启用自身账号")

    user.is_active = not user.is_active
    db.commit()

    action = "user_disable" if not user.is_active else "user_enable"
    write_audit_log(
        db,
        actor=current_user.username,
        action=action,
        target_type="user",
        target_id=user.id,
        detail=f"用户 {user.username} 已{'禁用' if not user.is_active else '启用'}",
        ip=get_client_ip(http_request),
    )
    return ToggleActiveResponse(
        id=user.id,
        username=user.username,
        is_active=user.is_active,
        message=f"用户 {user.username} 已{'禁用' if not user.is_active else '启用'}",
    )


# ------------------------------- 安全审计 -------------------------------


@router.get("/audit-logs", response_model=AuditLogResponse)
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: str | None = None,
    q: str | None = None,
    _: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        query = db.query(AuditLog)
        if action and action.strip():
            query = query.filter(AuditLog.action == action.strip())
        if q and q.strip():
            like = f"%{q.strip()}%"
            query = query.filter(
                (AuditLog.actor.ilike(like))
                | (AuditLog.detail.ilike(like))
                | (AuditLog.target_id.ilike(like))
            )
        total = query.count()
        items = (
            query.order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        logs = [
            AuditLogItem(
                id=l.id,
                actor=l.actor,
                actor_role=l.actor_role,
                action=l.action,
                target_type=l.target_type,
                target_id=l.target_id,
                detail=l.detail,
                ip=l.ip,
                created_at=_iso(l.created_at),
            )
            for l in items
        ]
        return AuditLogResponse(logs=logs, total=total, page=page, page_size=page_size)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取审计日志失败: {exc}")
