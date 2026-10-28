<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="logo-icon"><i class="fas fa-wand-magic-sparkles"></i></div>
      <div class="brand-copy">
        <h2>NovaChat</h2>
        <span>星智问答</span>
      </div>
    </div>
    <nav class="sidebar-nav">
      <div class="nav-label">智能工作区</div>
      <button @click="onNewChat" :class="['nav-btn', { active: chatStore.activeNav === 'newChat' }]">
        <i class="fas fa-plus"></i> 新建会话
      </button>
      <button @click="onHistory" :class="['nav-btn', { active: chatStore.activeNav === 'history' }]">
        <i class="fas fa-history"></i> 历史记录
      </button>
      <button v-if="authStore.isAdmin" @click="onSettings" :class="['nav-btn', { active: chatStore.activeNav === 'settings' }]">
        <i class="fas fa-database"></i> 知识库
      </button>
    </nav>
    <div class="sidebar-footer">
      <button @click="chatStore.handleClearChat" class="danger-btn">
        <i class="fas fa-trash-alt"></i> 清空当前对话
      </button>
      <div v-if="authStore.isAuthenticated" class="user-badge">
        <div class="user-avatar">{{ authStore.currentUser?.username?.slice(0, 1).toUpperCase() }}</div>
        <div>
          <span>{{ authStore.currentUser?.username }}</span>
          <small>{{ roleLabel }}</small>
        </div>
      </div>
      <button v-if="authStore.isAuthenticated" @click="authStore.handleLogout" class="danger-btn logout-btn">
        <i class="fas fa-right-from-bracket"></i> 退出登录
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { useChatStore } from '@/stores/chat';
import { useSessionStore } from '@/stores/sessions';

const authStore = useAuthStore();
const chatStore = useChatStore();
const sessionStore = useSessionStore();

const roleLabel = computed(() => {
  if (authStore.currentUser?.role === 'super_admin') return '超级管理员';
  if (authStore.currentUser?.role === 'admin') return '管理员';
  return '普通用户';
});

const onNewChat = () => {
  chatStore.handleNewChat();
};

const onHistory = async () => {
  chatStore.setActiveNav('history');
  sessionStore.showHistorySidebar = !sessionStore.showHistorySidebar;
  if (sessionStore.showHistorySidebar) {
    try {
      await sessionStore.fetchSessions();
      chatStore.mergeCachedSessionsIntoHistory();
    } catch (error: any) {
      alert(error.message);
    }
  }
};

const onSettings = () => {
  if (!authStore.isAdmin) {
    alert('仅管理员可访问文档管理');
    return;
  }
  chatStore.setActiveNav('settings');
  sessionStore.showHistorySidebar = false;
};
</script>
