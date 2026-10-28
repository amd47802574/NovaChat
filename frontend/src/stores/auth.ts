import { defineStore } from 'pinia';
import api from '@/utils/api';
import type { CurrentUser } from '@/types/user';

const clearLastSessionUrlParam = () => {
  if (typeof window === 'undefined' || !window.history?.replaceState) return;
  try {
    const url = new URL(window.location.href);
    if (!url.searchParams.has('session_id')) return;
    url.searchParams.delete('session_id');
    window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`);
  } catch (_) {
    // URL 清理失败时不影响退出登录。
  }
};

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('accessToken') || '',
    currentUser: null as CurrentUser | null,
    authMode: 'login' as 'login' | 'register',
    authForm: {
      username: '',
      password: '',
      confirm_password: '',
      role: 'user' as 'user' | 'admin' | 'super_admin',
      admin_code: '',
    },
    authLoading: false,
  }),

  getters: {
    isAuthenticated(): boolean {
      return !!this.token && !!this.currentUser;
    },
    isAdmin(): boolean {
      return this.currentUser?.role === 'admin';
    },
    isSuperAdmin(): boolean {
      return this.currentUser?.role === 'super_admin';
    },
  },

  actions: {
    async fetchMe() {
      if (!this.token) return;
      try {
        const response = await api.get('/auth/me');
        this.currentUser = response.data;
      } catch (error) {
        this.handleLogout();
        throw error;
      }
    },

    async handleAuthSubmit() {
      if (this.authLoading) return;
      const username = this.authForm.username.trim();
      const password = this.authForm.password.trim();
      if (!username || !password) {
        throw new Error('用户名和密码不能为空');
      }

      this.authLoading = true;
      try {
        const endpoint = this.authMode === 'login' ? '/auth/login' : '/auth/register';
        const payload: any = { username, password };
        if (this.authMode === 'register') {
          payload.role = this.authForm.role;
          payload.admin_code = this.authForm.admin_code || null;
        }

        const response = await api.post(endpoint, payload);
        const data = response.data;

        this.token = data.access_token;
        this.currentUser = { username: data.username, role: data.role };
        localStorage.setItem('accessToken', this.token);
        
        // Reset password fields
        this.authForm.password = '';
        this.authForm.confirm_password = '';
        this.authForm.admin_code = '';
      } catch (error: any) {
        const errMsg = error.response?.data?.detail || error.message || '认证失败';
        throw new Error(errMsg);
      } finally {
        this.authLoading = false;
      }
    },

    handleLogout() {
      this.token = '';
      this.currentUser = null;
      localStorage.removeItem('accessToken');
      localStorage.removeItem('novaLastSessionId');
      clearLastSessionUrlParam();
    },
  },
});
