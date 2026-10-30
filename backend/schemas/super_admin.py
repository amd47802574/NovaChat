from typing import Dict, List, Optional

from pydantic import BaseModel


# ----------------------------- 数据面板（Dashboard） -----------------------------


class TrendPoint(BaseModel):
    date: str
    count: int


class RoleCount(BaseModel):
    role: str
    count: int


class DashboardMetrics(BaseModel):
    # 用户规模
    total_users: int
    active_users: int
    disabled_users: int
    admin_users: int
    super_admin_users: int
    # 业务体量
    total_sessions: int
    total_messages: int
    total_documents: int
    # 时间维度趋势（近 7 天）
    registrations_last_7_days: List[TrendPoint]
    logins_last_7_days: List[TrendPoint]
    # 结构分布
    role_distribution: List[RoleCount]
    generated_at: str


# ----------------------------- 用户管理（User Management） -----------------------------


class AdminUserItem(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    is_locked: bool
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None
    updated_at: Optional[str] = None


class AdminUserDetail(AdminUserItem):
    failed_login_attempts: int
    locked_until: Optional[str] = None


class AdminUserListResponse(BaseModel):
    users: List[AdminUserItem]
    total: int
    page: int
    page_size: int


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: Optional[str] = "user"
    is_active: Optional[bool] = True


class UpdateUserRequest(BaseModel):
    # 仅传需要修改的字段；两者皆可单独或同时提交
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UpdateUserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    message: str


class ToggleActiveResponse(BaseModel):
    id: int
    username: str
    is_active: bool
    message: str


class ResetPasswordRequest(BaseModel):
    # 新密码：至少 6 位；重置后同时清除该账号的登录锁定状态
    new_password: str


class ResetPasswordResponse(BaseModel):
    id: int
    username: str
    message: str


# ----------------------------- 安全审计（Audit Log） -----------------------------


class AuditLogItem(BaseModel):
    id: int
    actor: str
    actor_role: str
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    detail: Optional[str] = None
    ip: Optional[str] = None
    created_at: Optional[str] = None


class AuditLogResponse(BaseModel):
    logs: List[AuditLogItem]
    total: int
    page: int
    page_size: int


# ----------------------------- 模型配置（Model Config） -----------------------------


class ModelConfigField(BaseModel):
    key: str
    label: str
    description: str
    is_secret: bool = False
    required: bool = True
    # 敏感字段恒为空字符串，is_set 指示是否已配置；非敏感字段回显当前值
    is_set: bool = False
    value: str = ""


class ModelConfigResponse(BaseModel):
    config: List[ModelConfigField]
    applied_at: Optional[str] = None


class UpdateModelConfigRequest(BaseModel):
    # 敏感字段：留空（或不传）表示沿用当前值，仅传入非空新值才覆盖
    ark_api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    grade_model: Optional[str] = None
    fast_model: Optional[str] = None


class UpdateModelConfigResponse(BaseModel):
    message: str
    applied_at: Optional[str] = None
