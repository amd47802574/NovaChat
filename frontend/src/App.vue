<template>
  <div class="app-wrapper" :class="{ unauthenticated: !authStore.isAuthenticated }">
    <main class="main-content">
      <AuthPanel v-if="!authStore.isAuthenticated" />

      <template v-else>
        <DocumentSettings v-if="chatStore.activeNav === 'settings'" />
        <HistorySidebar />
        <ChatArea v-show="chatStore.activeNav !== 'settings'" />
      </template>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue';
import AuthPanel from '@/components/AuthPanel.vue';
import HistorySidebar from '@/components/HistorySidebar.vue';
import ChatArea from '@/components/Chat/ChatArea.vue';
import DocumentSettings from '@/components/Documents/DocumentSettings.vue';

import { useAuthStore } from '@/stores/auth';
import { useChatStore } from '@/stores/chat';
import { useSessionStore } from '@/stores/sessions';

const authStore = useAuthStore();
const chatStore = useChatStore();
const sessionStore = useSessionStore();

const handleUnauthorized = () => {
  authStore.handleLogout();
  alert('登录已过期，请重新登录');
};

onMounted(async () => {
  window.addEventListener('unauthorized', handleUnauthorized);
  document.documentElement.dataset.theme = localStorage.getItem('novaTheme') || 'light';

  if (authStore.token) {
    try {
      await authStore.fetchMe();
      // 文档管理仅限管理员：非管理员若通过 URL 直达 settings 视图，恢复登录后切回聊天页。
      if (chatStore.activeNav === 'settings' && !authStore.isAdmin) {
        chatStore.setActiveNav('newChat');
      }
      try {
        await sessionStore.fetchSessions();
        chatStore.mergeCachedSessionsIntoHistory();
      } catch (_) {
        // 历史列表加载失败不影响恢复当前会话内容。
      }
      await chatStore.restoreLastSession();
    } catch (_) {
      authStore.handleLogout();
    }
  }
});

onUnmounted(() => {
  window.removeEventListener('unauthorized', handleUnauthorized);
});
</script>
