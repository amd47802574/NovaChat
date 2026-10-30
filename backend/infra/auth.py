import os
import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.infra.database import SessionLocal, get_db
from backend.db.models import User
from backend.infra.timezone import now_for_db

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-secret")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))
ADMIN_INVITE_CODE = os.getenv("ADMIN_INVITE_CODE", "")
# 超级管理员邀请码：仅用于注册时申请 super_admin 角色，与 admin 邀请码相互独立。
# 为空时不允许通过自助注册成为超级管理员（只能由已有超级管理员在后台创建）。
SUPER_ADMIN_INVITE_CODE = os.getenv("SUPER_ADMIN_INVITE_CODE", "")
PBKDF2_ROUNDS = int(os.getenv("PASSWORD_PBKDF2_ROUNDS", "310000"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_client_ip(request: "Request | None") -> str | None:
    """从请求中提取客户端真实 IP，兼容反向代理透传的 X-Forwarded-For。"""
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # X-Forwarded-For 可能为逗号分隔的多跳，取第一个即真实客户端
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return None

# 登录安全与错误提示相关配置
MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
LOCK_DURATION_MINUTES = int(os.getenv("LOGIN_LOCK_MINUTES", "15"))


class LoginError(Exception):
    """登录失败时的结构化异常，携带给前端展示的具体提示与 HTTP 状态码。"""

    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def verify_password(plain_password: str, password_hash: str) -> bool:
    if not plain_password or not password_hash:
        return False

    # New format: pbkdf2_sha256$<rounds>$<salt_b64>$<digest_b64>
    if password_hash.startswith("pbkdf2_sha256$"):
        try:
            _, rounds, salt_b64, digest_b64 = password_hash.split("$", 3)
            salt = base64.b64decode(salt_b64.encode("ascii"))
            expected = base64.b64decode(digest_b64.encode("ascii"))
            calculated = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                salt,
                int(rounds),
            )
            return hmac.compare_digest(calculated, expected)
        except Exception:
            return False

    # Backward compatibility for legacy passlib/bcrypt hashes.
    if password_hash.startswith("$2") or password_hash.startswith("$bcrypt"):
        try:
            from passlib.context import CryptContext

            legacy_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")
            return legacy_context.verify(plain_password, password_hash)
        except Exception:
            return False

    return False


def get_password_hash(password: str) -> str:
    if not password:
        raise ValueError("password is required")

    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ROUNDS,
    )
    salt_b64 = base64.b64encode(salt).decode("ascii")
    digest_b64 = base64.b64encode(digest).decode("ascii")
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt_b64}${digest_b64}"


def create_access_token(username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": username,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def authenticate_user(db: Session, username: str, password: str) -> User:
    """
    校验用户名与密码，返回已认证的用户对象；任意环节失败抛出 LoginError，
    其 message 即为面向用户的具体提示文案（用户名不存在 / 密码错误 /
    账号被锁定 / 账号被禁用等）。
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise LoginError("用户名不存在")

    now = now_for_db()

    # 临时锁定已到期：自动解除并清零失败计数，允许用户继续尝试
    if user.locked_until and user.locked_until <= now:
        user.is_locked = False
        user.locked_until = None
        user.failed_login_attempts = 0
        db.commit()

    # 账号被禁用（管理员操作）
    if not user.is_active:
        raise LoginError("该账号已被禁用，请联系管理员")

    # 账号被锁定
    if user.is_locked:
        if user.locked_until and user.locked_until > now:
            remain_minutes = max(1, int((user.locked_until - now).total_seconds() // 60))
            raise LoginError(f"该账号已被锁定，请于约 {remain_minutes} 分钟后再试，或联系管理员")
        raise LoginError("该账号已被锁定，请联系管理员")

    # 密码校验
    if not verify_password(password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
            user.is_locked = True
            user.locked_until = now + timedelta(minutes=LOCK_DURATION_MINUTES)
            db.commit()
            raise LoginError(
                f"密码连续错误次数过多，账号已被锁定 {LOCK_DURATION_MINUTES} 分钟，请稍后再试或联系管理员"
            )
        db.commit()
        remaining = MAX_LOGIN_ATTEMPTS - user.failed_login_attempts
        raise LoginError(f"密码错误，还可尝试 {remaining} 次")

    # 登录成功：清零失败计数与临时锁定位
    if user.failed_login_attempts or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()
    return user


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效或过期的认证令牌",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise credentials_exception
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    # 管理员及以上（admin 与 super_admin）均可访问；super_admin 拥有不低于管理员的全部治理权限。
    if current_user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="管理员权限不足")
    return current_user


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    """超级管理员依赖：仅 super_admin 角色可放行，其余一律 403。

    与普通 admin 完全隔离——普通管理员无法触碰用户管理、数据面板与审计接口。
    """
    if current_user.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="超级管理员权限不足")
    return current_user


def require_conversation_access(current_user: User = Depends(get_current_user)) -> User:
    """对话功能依赖：仅普通用户与管理员可访问；超级管理员为纯治理角色，不参与对话。

    与前端界面展示解耦——即便前端被绕过/篡改，后端仍在此处统一拒绝超级管理员的
    对话、会话与附件请求，确保「权限校验」始终是服务端权威，而非仅靠隐藏 UI。
    """
    if current_user.role == "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="超级管理员不可使用对话功能，请使用超级管理后台",
        )
    return current_user


def resolve_role(
    requested_role: str | None,
    admin_code: str | None,
    super_admin_code: str | None = None,
) -> str:
    """把注册请求中的角色诉求解析为最终落库角色。

    - 申请 super_admin：必须提供正确的超级管理员邀请码，否则 403。
    - 申请 admin：必须提供正确的管理员邀请码，否则 403。
    - 其它（含空）：一律降级为普通 user，不允许越权自提。
    """
    role = (requested_role or "user").strip().lower()
    if role == "super_admin":
        sac = super_admin_code if super_admin_code is not None else SUPER_ADMIN_INVITE_CODE
        if not sac:
            # 未配置公开邀请码：不允许自助注册，明确告知正确的创建途径，
            # 避免用户拿到模糊的「邀请码错误」。
            raise HTTPException(
                status_code=403,
                detail="超级管理员暂不开放公开注册：请配置 SUPER_ADMIN_INVITE_CODE 后凭邀请码注册，"
                "或由已有超级管理员在「超级管理后台 → 用户管理」中创建。",
            )
        if admin_code == sac:
            return "super_admin"
        raise HTTPException(status_code=403, detail="超级管理员邀请码错误")
    if role == "admin":
        if ADMIN_INVITE_CODE and admin_code == ADMIN_INVITE_CODE:
            return "admin"
        raise HTTPException(status_code=403, detail="管理员邀请码错误")
    return "user"
