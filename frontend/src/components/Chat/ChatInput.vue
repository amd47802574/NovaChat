<template>
  <div class="input-area-wrapper">
    <div v-if="chatStore.currentPendingHitl" class="hitl-panel">
      <div class="hitl-panel-header">
        <i class="fas fa-circle-question"></i>
        <span>需要你补充一下</span>
      </div>
      <div class="hitl-panel-prompt">{{ chatStore.currentPendingHitl.prompt }}</div>
      <div
        v-if="chatStore.currentPendingHitl.options && chatStore.currentPendingHitl.options.length"
        class="hitl-options"
      >
        <button
          v-for="option in chatStore.currentPendingHitl.options"
          :key="option"
          type="button"
          class="hitl-option"
          @click="selectHitlOption(option)"
        >
          {{ option }}
        </button>
      </div>
    </div>

    <div v-if="attachments.length" class="attachment-list">
      <div v-for="(attachment, index) in attachments" :key="attachment.key" class="attachment-chip">
        <div v-if="attachment.preview" class="attachment-preview">
          <img :src="attachment.preview" :alt="attachment.file.name" />
        </div>
        <i v-else class="far fa-file-lines"></i>
        <span>{{ attachment.file.name }}</span>
        <button type="button" title="移除附件" @click="removeAttachment(index)">
          <i class="fas fa-xmark"></i>
        </button>
      </div>
    </div>

    <div :class="['input-area', { 'hitl-active': chatStore.currentPendingHitl }]">
      <input
        ref="fileInputRef"
        class="file-input"
        type="file"
        accept="image/*,.pdf,.doc,.docx,.txt,.md,.xls,.xlsx"
        multiple
        @change="handleFiles"
      />
      <button
        class="attach-btn"
        type="button"
        title="添加图片或文件"
        :disabled="chatStore.isInputLocked"
        @click="fileInputRef?.click()"
      >
        <i class="fas fa-paperclip"></i>
      </button>

      <textarea 
        v-model="chatStore.userInput" 
        @keydown="handleKeyDown"
        @compositionstart="handleCompositionStart"
        @compositionend="handleCompositionEnd"
        @input="autoResize"
        :placeholder="chatStore.inputPlaceholder" 
        rows="1"
        ref="textareaRef"
        :disabled="chatStore.isInputLocked"
      ></textarea>
      
      <button 
        v-if="chatStore.isViewingStreamingSession" 
        @click="chatStore.handleStop" 
        class="send-btn stop-btn" 
        title="终止回答"
      >
        <i class="fas fa-stop"></i>
      </button>
      
      <button 
        v-else 
        @click="onSend" 
        class="send-btn" 
        :disabled="!canSend"
        :title="chatStore.isLoading ? '当前已有回答正在生成' : '发送'"
      >
        <i class="fas fa-arrow-up"></i>
      </button>
    </div>
    <div class="quick-prompts" aria-label="快捷提问">
      <button v-for="prompt in quickPrompts" :key="prompt" type="button" @click="selectPrompt(prompt)">
        {{ prompt }}
      </button>
    </div>
    <div class="footer-text"><i class="fas fa-shield-halved"></i> NovaChat 可能产生不准确的信息，请核验重要内容。</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, nextTick } from 'vue';
import { useChatStore } from '@/stores/chat';

const chatStore = useChatStore();
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);
const isComposing = ref(false);
type Attachment = { key: string; file: File; preview: string | null };
const attachments = ref<Attachment[]>([]);
const quickPrompts = [
  '帮我总结核心内容',
  '解释得更简单一些',
  '列出关键步骤',
  '对比不同观点',
  '给我一个示例',
];
const canSend = computed(() => {
  return !chatStore.isLoading && !chatStore.isInputLocked
    && (!!chatStore.userInput.trim() || attachments.value.length > 0);
});

const handleCompositionStart = () => {
  isComposing.value = true;
};

const handleCompositionEnd = () => {
  isComposing.value = false;
};

const handleKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey && !isComposing.value) {
    event.preventDefault();
    onSend();
  }
};

const autoResize = () => {
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto';
    textareaRef.value.style.height = textareaRef.value.scrollHeight + 'px';
  }
};

const resetTextareaHeight = () => {
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto';
  }
};

const revokePreview = (attachment: Attachment) => {
  if (attachment.preview) URL.revokeObjectURL(attachment.preview);
};

const handleFiles = (event: Event) => {
  const files = Array.from((event.target as HTMLInputElement).files || []);
  files.forEach((file) => {
    attachments.value.push({
      key: `${file.name}-${file.size}-${file.lastModified}`,
      file,
      preview: file.type.startsWith('image/') ? URL.createObjectURL(file) : null,
    });
  });
  if (fileInputRef.value) fileInputRef.value.value = '';
};

const removeAttachment = (index: number) => {
  const [removed] = attachments.value.splice(index, 1);
  if (removed) revokePreview(removed);
};

const selectPrompt = async (prompt: string) => {
  chatStore.userInput = prompt;
  await focusTextarea();
};

const focusTextarea = async () => {
  await nextTick();
  textareaRef.value?.focus();
  autoResize();
};

const selectHitlOption = async (option: string) => {
  chatStore.selectHitlOption(option);
  await focusTextarea();
};

const onSend = async () => {
  if (!canSend.value || isComposing.value) return;

  const attachmentText = attachments.value.length
    ? `\n\n附件：${attachments.value.map((item) => item.file.name).join('、')}`
    : '';
  chatStore.userInput = `${chatStore.userInput.trim() || '请分析这些附件'}${attachmentText}`;

  await chatStore.handleSend();

  attachments.value.forEach(revokePreview);
  attachments.value = [];
  await nextTick();
  resetTextareaHeight();
};

onBeforeUnmount(() => {
  attachments.value.forEach(revokePreview);
});
</script>
