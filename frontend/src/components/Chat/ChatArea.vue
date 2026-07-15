<template>
  <div class="chat-area">
    <header class="chat-header">
      <div class="header-info">
        <div class="status-dot"></div>
        <div>
          <strong>星智问答</strong>
          <span>智能引擎已就绪</span>
        </div>
      </div>
      <div class="header-model"><i class="fas fa-microchip"></i> Nova RAG</div>
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
import { ref, watch, nextTick, onBeforeUpdate, onMounted } from 'vue';
import WelcomeScreen from './WelcomeScreen.vue';
import MessageItem from './MessageItem.vue';
import ChatInput from './ChatInput.vue';
import { useChatStore } from '@/stores/chat';

const chatStore = useChatStore();
const chatContainerRef = ref<HTMLDivElement | null>(null);
const messageItemRefs = ref<any[]>([]);

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
