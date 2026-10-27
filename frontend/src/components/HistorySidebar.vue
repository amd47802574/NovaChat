<template>
  <Teleport to="body">
    <Transition name="drawer-fade">
      <div
        v-if="sessionStore.showHistorySidebar"
        class="drawer-layer"
        @click.self="closeDrawer"
        @touchstart.passive="onDrawerTouchStart"
        @touchend.passive="onDrawerTouchEnd"
      >
        <aside class="history-sidebar" aria-label="历史会话">
          <div class="history-header">
            <div class="header-titles">
              <span class="drawer-brand">NovaChat</span>
              <h3>全部对话</h3>
            </div>
            <div class="header-actions">
              <button
                v-if="!selectMode"
                class="batch-manage-btn"
                type="button"
                title="批量管理会话"
                @click="enterSelectMode"
              >
                <i class="far fa-square-check"></i>
                <span>批量管理</span>
              </button>
              <button v-else class="batch-cancel-btn" type="button" @click="exitSelectMode">
                <span>取消</span>
              </button>
              <button class="close-btn" type="button" title="关闭侧边栏" @click="closeDrawer">
                <i class="fas fa-xmark"></i>
              </button>
            </div>
          </div>

          <div v-if="selectMode" class="batch-toolbar">
            <button class="batch-select-all" type="button" @click="toggleSelectAll">
              <span class="select-checkbox" :class="{ checked: allSelected }">
                <i v-if="allSelected" class="fas fa-check"></i>
              </span>
              <span>全选</span>
              <span class="batch-count">已选 {{ selectedCount }}</span>
            </button>
            <button
              class="batch-delete-btn"
              type="button"
              :disabled="selectedCount === 0"
              @click="onBatchDelete"
            >
              <i class="far fa-trash-can"></i>
              <span>删除{{ selectedCount > 0 ? ` (${selectedCount})` : '' }}</span>
            </button>
          </div>

          <div class="history-list">
            <div v-if="sessionStore.isHistoryLoading" class="history-loading">
              <span></span><span></span><span></span>
            </div>
            <div v-else-if="sortedSessions.length === 0" class="empty-history">
              <i class="far fa-message"></i>
              <p>还没有历史对话</p>
            </div>

            <div
              v-for="session in sortedSessions"
              :key="session.session_id"
              class="history-swipe-row"
              :class="{
                revealed: !selectMode && swipedSessionId === session.session_id,
                'menu-open': !selectMode && openMenuId === session.session_id,
                'select-mode': selectMode,
                selected: selectMode && selectedIds.includes(session.session_id),
              }"
              @touchstart.passive="onItemTouchStart($event, session.session_id)"
              @touchend.passive="onItemTouchEnd($event, session.session_id)"
            >
              <button
                v-if="!selectMode"
                class="swipe-delete-btn"
                type="button"
                title="删除会话"
                @click="onDeleteSession(session.session_id)"
              >
                <i class="far fa-trash-can"></i>
              </button>
              <div
                class="history-item"
                :class="{ active: session.session_id === chatStore.sessionId }"
                @click="selectMode ? toggleSelect(session.session_id) : onLoadSession(session.session_id)"
              >
                <span
                  v-if="selectMode"
                  class="select-checkbox"
                  :class="{ checked: selectedIds.includes(session.session_id), disabled: session.isStreaming }"
                  @click.stop="toggleSelect(session.session_id)"
                >
                  <i v-if="selectedIds.includes(session.session_id)" class="fas fa-check"></i>
                </span>
                <i v-if="session.pinned" class="fas fa-thumbtack pinned-icon"></i>
                <div class="session-info">
                  <div class="session-title">{{ session.title || '未命名对话' }}</div>
                  <div class="session-meta">
                    <span>{{ formatTime(session.updated_at) }}</span>
                    <span v-if="session.isStreaming" class="session-status">生成中</span>
                  </div>
                </div>
                <button
                  v-if="!selectMode"
                  class="session-more-btn"
                  type="button"
                  title="会话操作"
                  @click.stop="toggleMenu(session.session_id)"
                >
                  <i class="fas fa-ellipsis"></i>
                </button>
                <Transition name="menu-pop">
                  <div v-if="!selectMode && openMenuId === session.session_id" class="session-menu" @click.stop>
                    <button type="button" @click="onRenameSession(session.session_id)">
                      <i class="far fa-pen-to-square"></i>重命名
                    </button>
                    <button type="button" @click="onTogglePin(session.session_id)">
                      <i class="fas fa-thumbtack"></i>{{ session.pinned ? '取消置顶' : '置顶' }}
                    </button>
                    <button class="danger-menu-item" type="button" @click="onDeleteSession(session.session_id)">
                      <i class="far fa-trash-can"></i>删除
                    </button>
                  </div>
                </Transition>
              </div>
            </div>
          </div>

          <div class="history-footer">
            <button type="button" @click="toggleTheme">
              <i :class="isDark ? 'far fa-sun' : 'far fa-moon'"></i>
              <span>{{ isDark ? '浅色模式' : '深色模式' }}</span>
            </button>
            <button v-if="authStore.isAdmin" type="button" @click="openSettings">
              <i class="fas fa-sliders"></i>
              <span>设置</span>
            </button>
            <button class="clear-history-btn" type="button" @click="onClearAll">
              <i class="far fa-trash-can"></i>
              <span>清空全部历史</span>
            </button>
            <div class="drawer-user">
              <span>{{ authStore.currentUser?.username }}</span>
              <button type="button" title="退出登录" @click="authStore.handleLogout">
                <i class="fas fa-arrow-right-from-bracket"></i>
              </button>
            </div>
          </div>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { useChatStore } from '@/stores/chat';
import { useSessionStore } from '@/stores/sessions';

const authStore = useAuthStore();
const chatStore = useChatStore();
const sessionStore = useSessionStore();
const openMenuId = ref<string | null>(null);
const swipedSessionId = ref<string | null>(null);
const touchStartX = ref(0);
const drawerTouchStartX = ref(0);
const isDark = ref(document.documentElement.dataset.theme === 'dark');
const selectMode = ref(false);
const selectedIds = ref<string[]>([]);

const sortedSessions = computed(() => {
  return [...sessionStore.sessions].sort((a, b) => {
    if (!!a.pinned !== !!b.pinned) return a.pinned ? -1 : 1;
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
  });
});

// 批量模式下可选中的会话（生成中的会话不可删除，需排除）。
const selectableSessions = computed(() => sortedSessions.value.filter((s) => !s.isStreaming));
const allSelected = computed(
  () =>
    selectableSessions.value.length > 0 &&
    selectableSessions.value.every((s) => selectedIds.value.includes(s.session_id))
);
const selectedCount = computed(() => selectedIds.value.length);

const closeDrawer = () => {
  sessionStore.showHistorySidebar = false;
  openMenuId.value = null;
  swipedSessionId.value = null;
  selectMode.value = false;
  selectedIds.value = [];
};

const enterSelectMode = () => {
  openMenuId.value = null;
  swipedSessionId.value = null;
  selectedIds.value = [];
  selectMode.value = true;
};

const exitSelectMode = () => {
  selectMode.value = false;
  selectedIds.value = [];
};

const toggleSelect = (sessionId: string) => {
  const session = sessionStore.sessions.find((item) => item.session_id === sessionId);
  if (!session || session.isStreaming) return;
  const index = selectedIds.value.indexOf(sessionId);
  if (index >= 0) selectedIds.value.splice(index, 1);
  else selectedIds.value.push(sessionId);
};

const toggleSelectAll = () => {
  if (allSelected.value) {
    selectedIds.value = [];
  } else {
    selectedIds.value = selectableSessions.value.map((s) => s.session_id);
  }
};

const onBatchDelete = async () => {
  const deletable = selectedIds.value.filter((id) => {
    const session = sessionStore.sessions.find((item) => item.session_id === id);
    return session && !session.isStreaming;
  });
  if (!deletable.length) {
    alert('请先选择要删除的会话');
    return;
  }
  if (!confirm(`确定删除选中的 ${deletable.length} 个会话吗？此操作无法撤销。`)) return;

  try {
    await sessionStore.deleteSessions(deletable);
    deletable.forEach((id) => {
      delete chatStore.messagesBySession[id];
      delete chatStore.pendingHitlBySession[id];
    });
    if (deletable.includes(chatStore.sessionId)) chatStore.handleNewChat();
    exitSelectMode();
  } catch (error: any) {
    alert('批量删除失败：' + error.message);
  }
};

const formatTime = (value: string) => {
  const date = new Date(value);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  }
  return date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
};

const toggleMenu = (sessionId: string) => {
  swipedSessionId.value = null;
  openMenuId.value = openMenuId.value === sessionId ? null : sessionId;
};

const onLoadSession = async (sessionId: string) => {
  if (swipedSessionId.value === sessionId) {
    swipedSessionId.value = null;
    return;
  }
  try {
    await chatStore.loadSession(sessionId);
  } catch (error: any) {
    alert('加载会话失败：' + error.message);
  }
};

const onRenameSession = async (sessionId: string) => {
  openMenuId.value = null;
  const session = sessionStore.sessions.find((item) => item.session_id === sessionId);
  if (!session || session.isStreaming) {
    alert('回答生成完成后才能重命名');
    return;
  }
  const nextTitle = prompt('输入新的会话名称', session.title || '')?.trim();
  if (!nextTitle || nextTitle === session.title) return;
  try {
    await sessionStore.updateSession(sessionId, { title: nextTitle });
  } catch (error: any) {
    alert(error.message);
  }
};

const onTogglePin = async (sessionId: string) => {
  openMenuId.value = null;
  const session = sessionStore.sessions.find((item) => item.session_id === sessionId);
  if (!session || session.isStreaming) {
    alert('回答生成完成后才能置顶');
    return;
  }
  try {
    await sessionStore.updateSession(sessionId, { pinned: !session.pinned });
  } catch (error: any) {
    alert(error.message);
  }
};

const onDeleteSession = async (sessionId: string) => {
  openMenuId.value = null;
  swipedSessionId.value = null;
  if (chatStore.streamingSessionId === sessionId) {
    alert('该会话正在生成回答，请先终止或等待完成');
    return;
  }
  const sessionLabel = sessionStore.sessions.find((item) => item.session_id === sessionId)?.title || '该会话';
  if (!confirm(`确定删除“${sessionLabel}”吗？`)) return;

  try {
    await sessionStore.deleteSession(sessionId);
    delete chatStore.messagesBySession[sessionId];
    delete chatStore.pendingHitlBySession[sessionId];
    if (chatStore.sessionId === sessionId) chatStore.handleNewChat();
  } catch (error: any) {
    alert('删除会话失败：' + error.message);
  }
};

const onClearAll = async () => {
  if (chatStore.isLoading) {
    alert('有回答正在生成，请先终止或等待完成');
    return;
  }
  if (!sessionStore.sessions.length || !confirm('确定清空全部历史会话吗？此操作无法撤销。')) return;
  try {
    await sessionStore.clearSessions();
    chatStore.messagesBySession = {};
    chatStore.pendingHitlBySession = {};
    chatStore.handleNewChat();
  } catch (error: any) {
    alert(error.message);
  }
};

const toggleTheme = () => {
  isDark.value = !isDark.value;
  const theme = isDark.value ? 'dark' : 'light';
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('novaTheme', theme);
};

const openSettings = () => {
  chatStore.setActiveNav('settings');
  closeDrawer();
};

const onItemTouchStart = (event: TouchEvent, sessionId: string) => {
  if (selectMode.value) return;
  touchStartX.value = event.changedTouches[0]?.clientX || 0;
  if (swipedSessionId.value !== sessionId) swipedSessionId.value = null;
};

const onItemTouchEnd = (event: TouchEvent, sessionId: string) => {
  if (selectMode.value) return;
  const endX = event.changedTouches[0]?.clientX || 0;
  const distance = endX - touchStartX.value;
  if (distance < -46) swipedSessionId.value = sessionId;
  if (distance > 36) swipedSessionId.value = null;
};

const onDrawerTouchStart = (event: TouchEvent) => {
  drawerTouchStartX.value = event.changedTouches[0]?.clientX || 0;
};

const onDrawerTouchEnd = (event: TouchEvent) => {
  const endX = event.changedTouches[0]?.clientX || 0;
  if (endX - drawerTouchStartX.value < -70) closeDrawer();
};
</script>
