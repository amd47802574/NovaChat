export type UserRole = 'user' | 'admin' | 'super_admin';

export interface CurrentUser {
  username: string;
  role: UserRole;
}

// ----------------------------- 数据面板（Dashboard） -----------------------------

export interface TrendPoint {
  date: string;
  count: number;
}

export interface RoleCount {
  role: string;
  count: number;
}

export interface DashboardMetrics {
  total_users: number;
  active_users: number;
  disabled_users: number;
  admin_users: number;
  super_admin_users: number;
  total_sessions: number;
  total_messages: number;
  total_documents: number;
  registrations_last_7_days: TrendPoint[];
  logins_last_7_days: TrendPoint[];
  role_distribution: RoleCount[];
  generated_at: string;
}

// ----------------------------- 用户管理（User Management） -----------------------------

export interface AdminUserItem {
  id: number;
  username: string;
  role: UserRole;
  is_active: boolean;
  is_locked: boolean;
  created_at: string | null;
  last_login_at: string | null;
  updated_at: string | null;
}

export interface AdminUserDetail extends AdminUserItem {
  failed_login_attempts: number;
  locked_until: string | null;
}

export interface AdminUserListResponse {
  users: AdminUserItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateUserRequest {
  username: string;
  password: string;
  role?: UserRole;
  is_active?: boolean;
}

export interface UpdateUserRequest {
  role?: UserRole;
  is_active?: boolean;
}

export interface UpdateUserResponse {
  id: number;
  username: string;
  role: UserRole;
  is_active: boolean;
  message: string;
}

export interface ToggleActiveResponse {
  id: number;
  username: string;
  is_active: boolean;
  message: string;
}

export interface ResetPasswordRequest {
  new_password: string;
}

export interface ResetPasswordResponse {
  id: number;
  username: string;
  message: string;
}

// ----------------------------- 安全审计（Audit Log） -----------------------------

export interface AuditLogItem {
  id: number;
  actor: string;
  actor_role: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  detail: string | null;
  ip: string | null;
  created_at: string | null;
}

export interface AuditLogResponse {
  logs: AuditLogItem[];
  total: number;
  page: number;
  page_size: number;
}

// ----------------------------- 模型配置（Model Config） -----------------------------

export interface ModelConfigField {
  key: string;
  label: string;
  description: string;
  is_secret: boolean;
  required: boolean;
  // 敏感字段恒为空；is_set 指示是否已配置；非敏感字段回显当前值
  is_set: boolean;
  value: string;
}

export interface ModelConfigResponse {
  config: ModelConfigField[];
  applied_at: string | null;
}

export interface UpdateModelConfigRequest {
  ark_api_key?: string;
  base_url?: string;
  model?: string;
  grade_model?: string;
  fast_model?: string;
}

export interface UpdateModelConfigResponse {
  message: string;
  applied_at: string | null;
}
