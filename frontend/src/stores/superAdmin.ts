import { defineStore } from 'pinia';
import api from '@/utils/api';
import type {
  AdminUserItem,
  AuditLogItem,
  CreateUserRequest,
  DashboardMetrics,
  ModelConfigField,
  ModelConfigResponse,
  UpdateModelConfigRequest,
  UpdateModelConfigResponse,
  UpdateUserRequest,
  UserRole,
} from '@/types/user';

const handleError = (error: any): never => {
  const msg = error?.response?.data?.detail || error?.message || '操作失败';
  throw new Error(msg);
};

export const useSuperAdminStore = defineStore('superAdmin', {
  state: () => ({
    // 数据面板
    metrics: null as DashboardMetrics | null,
    metricsLoading: false,
    // 用户管理
    users: [] as AdminUserItem[],
    usersTotal: 0,
    usersPage: 1,
    usersPageSize: 20,
    usersSearch: '',
    usersLoading: false,
    usersFetchSeq: 0,
    usersError: '' as string,
    // 安全审计
    auditLogs: [] as AuditLogItem[],
    auditTotal: 0,
    auditPage: 1,
    auditPageSize: 50,
    auditAction: '' as string,
    auditSearch: '' as string,
    auditLoading: false,
    // 模型配置
    modelConfig: [] as ModelConfigField[],
    modelConfigAppliedAt: null as string | null,
    modelConfigLoading: false,
  }),

  actions: {
    // --------------------------- 数据面板 ---------------------------
    async fetchMetrics() {
      this.metricsLoading = true;
      try {
        const { data } = await api.get('/super-admin/metrics');
        this.metrics = data;
      } catch (error) {
        handleError(error);
      } finally {
        this.metricsLoading = false;
      }
    },

    // --------------------------- 用户管理 ---------------------------
    async fetchUsers() {
      const seq = ++this.usersFetchSeq;
      this.usersLoading = true;
      this.usersError = '';
      try {
        const params: Record<string, any> = {
          page: this.usersPage,
          page_size: this.usersPageSize,
        };
        if (this.usersSearch.trim()) params.q = this.usersSearch.trim();
        const { data } = await api.get('/super-admin/users', { params });
        if (seq !== this.usersFetchSeq) return;
        this.users = data.users;
        this.usersTotal = data.total;
      } catch (error: any) {
        if (seq !== this.usersFetchSeq) return;
        this.usersError = error?.response?.data?.detail || error?.message || '网络异常，请稍后重试';
        handleError(error);
      } finally {
        if (seq === this.usersFetchSeq) this.usersLoading = false;
      }
    },

    setUsersSearch(value: string) {
      this.usersSearch = value;
      this.usersPage = 1;
      return this.fetchUsers();
    },

    setUsersPage(page: number) {
      this.usersPage = page;
      return this.fetchUsers();
    },

    async createUser(payload: CreateUserRequest) {
      try {
        const { data } = await api.post('/super-admin/users', payload);
        await this.fetchUsers();
        return data as { message: string };
      } catch (error) {
        return handleError(error);
      }
    },

    async updateUser(userId: number, payload: UpdateUserRequest) {
      try {
        const { data } = await api.put(`/super-admin/users/${userId}`, payload);
        await this.fetchUsers();
        return data as { message: string };
      } catch (error) {
        return handleError(error);
      }
    },

    async toggleUserActive(userId: number) {
      try {
        const { data } = await api.post(`/super-admin/users/${userId}/toggle-active`);
        await this.fetchUsers();
        return data as { message: string };
      } catch (error) {
        return handleError(error);
      }
    },

    // --------------------------- 安全审计 ---------------------------
    async fetchAuditLogs() {
      this.auditLoading = true;
      try {
        const params: Record<string, any> = {
          page: this.auditPage,
          page_size: this.auditPageSize,
        };
        if (this.auditAction.trim()) params.action = this.auditAction.trim();
        if (this.auditSearch.trim()) params.q = this.auditSearch.trim();
        const { data } = await api.get('/super-admin/audit-logs', { params });
        this.auditLogs = data.logs;
        this.auditTotal = data.total;
      } catch (error) {
        handleError(error);
      } finally {
        this.auditLoading = false;
      }
    },

    setAuditFilter(action: string, search: string) {
      this.auditAction = action;
      this.auditSearch = search;
      this.auditPage = 1;
      return this.fetchAuditLogs();
    },

    setAuditPage(page: number) {
      this.auditPage = page;
      return this.fetchAuditLogs();
    },

    // --------------------------- 模型配置 ---------------------------
    async fetchModelConfig() {
      this.modelConfigLoading = true;
      try {
        const { data } = await api.get<ModelConfigResponse>('/super-admin/model-config');
        this.modelConfig = data.config;
        this.modelConfigAppliedAt = data.applied_at;
      } catch (error) {
        handleError(error);
      } finally {
        this.modelConfigLoading = false;
      }
    },

    async updateModelConfig(payload: UpdateModelConfigRequest) {
      const { data } = await api.put<UpdateModelConfigResponse>('/super-admin/model-config', payload);
      // 保存后刷新本地展示（敏感字段回显为空，避免明文残留在前端状态）
      await this.fetchModelConfig();
      return data;
    },
  },
});

export const ROLE_LABELS: Record<UserRole, string> = {
  user: '普通用户',
  admin: '管理员',
  super_admin: '超级管理员',
};
