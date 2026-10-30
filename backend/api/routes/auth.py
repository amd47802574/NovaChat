from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.db.models import User
from backend.infra.audit import write_audit_log
from backend.infra.auth import (
    LoginError,
    authenticate_user,
    create_access_token,
    get_client_ip,
    get_current_user,
    get_db,
    get_password_hash,
    resolve_role,
)
from backend.infra.timezone import now_for_db
from backend.schemas import AuthResponse, CurrentUserResponse, LoginRequest, RegisterRequest

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=AuthResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    username = (request.username or "").strip()
    password = (request.password or "").strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    exists = db.query(User).filter(User.username == username).first()
    if exists:
        raise HTTPException(status_code=409, detail="用户名已存在")

    role = resolve_role(request.role, request.admin_code)
    user = User(username=username, password_hash=get_password_hash(password), role=role)
    db.add(user)
    db.commit()

    write_audit_log(
        db,
        actor=username,
        actor_role=role,
        action="user_register",
        target_type="user",
        target_id=user.id,
        detail=f"自助注册为 {role}",
    )

    token = create_access_token(username=username, role=role)
    return AuthResponse(access_token=token, username=username, role=role)


@router.post("/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest, http_request: Request, db: Session = Depends(get_db)):
    ip = get_client_ip(http_request)
    try:
        user = authenticate_user(db, request.username, request.password)
    except LoginError as exc:
        # 登录失败也留痕，便于发现暴力破解与异常登录
        write_audit_log(
            db,
            actor=(request.username or "").strip() or "unknown",
            actor_role="unknown",
            action="login_failed",
            target_type="user",
            detail=exc.message,
            ip=ip,
        )
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    # 记录最近登录时间（用于数据面板活跃度统计），失败计数由 authenticate_user 清零
    user.last_login_at = now_for_db()
    db.commit()

    write_audit_log(
        db,
        actor=user.username,
        actor_role=user.role,
        action="login",
        target_type="user",
        target_id=user.id,
        ip=ip,
    )

    token = create_access_token(username=user.username, role=user.role)
    return AuthResponse(access_token=token, username=user.username, role=user.role)


@router.get("/auth/me", response_model=CurrentUserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return CurrentUserResponse(username=current_user.username, role=current_user.role)
