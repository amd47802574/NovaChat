import { defineStore } from 'pinia';
import api from '@/utils/api';
import type { ChatSession } from '@/types/chat';

export const useSessionStore = defineStore('sessions', {
  state: () => ({
    sessions: [] as ChatSession[],
    showHistorySidebar: false,
    isHistoryLoading: false,
  }),

  actions: {
    async fetchSessions() {
      this.isHistoryLoading = true;
      try {
        const response = await api.get('/sessions');
        this.sessions = response.data.sessions || [];
      } catch (error: any) {
        const errMsg = error.response?.data?.detail || error.message || '加载历史记录失败';
        throw new Error(errMsg);
      } finally {
        this.isHistoryLoading = false;
      }
    },

    async deleteSession(sessionId: string) {
      try {
        const response = await api.delete(`/sessions/${encodeURIComponent(sessionId)}`);
        this.sessions = this.sessions.filter((s) => s.session_id !== sessionId);
        return response.data.message || '会话已删除';
      } catch (error: any) {
        const errMsg = error.response?.data?.detail || error.message || '删除会话失败';
        throw new Error(errMsg);
      }
    },

    async updateSession(sessionId: string, updates: { title?: string; pinned?: boolean }) {
      try {
        const response = await api.patch(`/sessions/${encodeURIComponent(sessionId)}`, updates);
        const target = this.sessions.find((session) => session.session_id === sessionId);
        if (target) {
          target.title = response.data.title;
          target.pinned = response.data.pinned;
        }
        this.sortSessions();
        return response.data.message || '会话已更新';
      } catch (error: any) {
        const errMsg = error.response?.data?.detail || error.message || '更新会话失败';
        throw new Error(errMsg);
      }
    },

    async clearSessions() {
      try {
        const response = await api.delete('/sessions');
        this.sessions = [];
        return response.data.message || '历史会话已清空';
      } catch (error: any) {
        const errMsg = error.response?.data?.detail || error.message || '清空历史会话失败';
        throw new Error(errMsg);
      }
    },

    async deleteSessions(sessionIds: string[]) {
      if (!sessionIds.length) return 0;
      try {
        const response = await api.delete('/sessions/batch', {
          data: { session_ids: sessionIds },
        });
        const deletedIds = new Set(sessionIds);
        this.sessions = this.sessions.filter((s) => !deletedIds.has(s.session_id));
        return response.data.deleted_count ?? sessionIds.length;
      } catch (error: any) {
        const errMsg = error.response?.data?.detail || error.message || '批量删除会话失败';
        throw new Error(errMsg);
      }
    },

    sortSessions() {
      this.sessions.sort((a, b) => {
        if (!!a.pinned !== !!b.pinned) return a.pinned ? -1 : 1;
        return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
      });
    },
  },
});
