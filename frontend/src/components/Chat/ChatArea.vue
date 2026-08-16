<template>
  <div class="chat-area">
    <header class="chat-header">
      <button class="top-icon-btn menu-trigger" type="button" title="打开历史会话" @click="openHistory">
        <i class="fas fa-bars"></i>
      </button>
      <div class="header-brand" aria-label="NovaChat">
        <span>NovaChat</span>
        <small>{{ currentTitle }}</small>
      </div>
      <div class="header-actions">
        <a
          class="top-icon-btn github-link"
          href="https://github.com/amd47802574/NovaChat"
          target="_blank"
          rel="noopener noreferrer"
          title="GitHub 仓库"
        >
          <i class="fab fa-github"></i>
        </a>
        <button class="new-chat-btn" type="button" title="新建对话" @click="createNewChat">
          <i class="fas fa-plus"></i>
        </button>
      </div>
    </header>

    <div class="chat-container" ref="chatContainerRef">
      <WelcomeScreen v-if="chatStore.messages.length === 0" />
      
      <MessageItem 
        v-for="(msg, index) in chatStore.messages" 
        :key="index" 
        :msg="msg" 
        :msg-index="index" 
        :ref="(el) => { if (el) messageItemRefs[index] = el; }"
        @cite-click="scrollToChunk"
      />
    </div>

    <ChatInput />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick, onBeforeUpdate, onMounted } from 'vue';
import WelcomeScreen from './WelcomeScreen.vue';
import MessageItem from './MessageItem.vue';
import ChatInput from './ChatInput.vue';
import { useChatStore } from '@/stores/chat';
import { useSessionStore } from '@/stores/sessions';

const chatStore = useChatStore();
const sessionStore = useSessionStore();
const chatContainerRef = ref<HTMLDivElement | null>(null);
const messageItemRefs = ref<any[]>([]);
const currentTitle = computed(() => {
  const session = sessionStore.sessions.find((item) => item.session_id === chatStore.sessionId);
  return session?.title || '全新对话';
});

const openHistory = async () => {
  sessionStore.showHistorySidebar = true;
  try {
    await sessionStore.fetchSessions();
    chatStore.mergeCachedSessionsIntoHistory();
  } catch (error: any) {
    alert(error.message);
  }
};

const createNewChat = () => {
  chatStore.handleNewChat();
};

onBeforeUpdate(() => {
  messageItemRefs.value = [];
});

const scrollToBottom = () => {
  if (chatContainerRef.value) {
    chatContainerRef.value.scrollTop = chatContainerRef.value.scrollHeight;
  }
};

const scrollToChunk = async (msgIndex: number, chunkIndex: number) => {
  const msgItem = messageItemRefs.value[msgIndex];
  if (!msgItem) return;

  // 展开参考资料区域
  msgItem.openReferences();

  await nextTick();
  const chunkEl = document.getElementById(`chunk-${msgIndex}-${chunkIndex}`);
  if (chunkEl) {
    chunkEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    chunkEl.classList.add('highlight-chunk');
    setTimeout(() => {
      chunkEl.classList.remove('highlight-chunk');
    }, 2000);
  }
};

// 消息变化或流式输出时自动滚动到底部
watch(
  () => chatStore.messages,
  () => {
    nextTick(() => {
      scrollToBottom();
    });
  },
  { deep: true }
);

onMounted(() => {
  scrollToBottom();
});
</script>
