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

    <div v-if="attachmentError" class="attachment-error">
      <i class="fas fa-triangle-exclamation"></i>
      <span>{{ attachmentError }}</span>
      <button type="button" title="关闭提示" @click="attachmentError = ''">
        <i class="fas fa-xmark"></i>
      </button>
    </div>

    <div v-if="attachments.length" class="attachment-list">
      <div v-for="attachment in attachments" :key="attachment.key" class="attachment-chip">
        <div v-if="attachment.preview" class="attachment-preview">
          <img :src="attachment.preview" :alt="attachment.file.name" />
        </div>
        <i v-else :class="fileIcon(attachment.file.name)"></i>
        <span>{{ attachment.file.name }}</span>
        <span v-if="attachment.status === 'uploading'" class="attachment-status">
          <i class="fas fa-spinner fa-spin"></i>
        </span>
        <span v-else-if="attachment.status === 'failed'" class="attachment-status failed" title="上传失败">
          <i class="fas fa-circle-exclamation"></i>
        </span>
        <button type="button" title="移除附件" @click="removeAttachment(attachment)">
          <i class="fas fa-xmark"></i>
        </button>
      </div>
    </div>

    <div :class="['input-area', { 'hitl-active': chatStore.currentPendingHitl }]">
      <input
        ref="fileInputRef"
        class="file-input"
        type="file"
        :accept="ACCEPT_ATTR"
        multiple
        @change="handleFiles"
      />
      <button
        class="attach-btn"
        type="button"
        aria-label="添加图片或文件"
        :title="isUploading ? '附件上传中…' : (visionEnabled ? '添加图片或文件' : '添加文件（当前模型不支持图片）')"
        :disabled="chatStore.isInputLocked || isUploading"
        @click="fileInputRef?.click()"
      >
        <i :class="isUploading ? 'fas fa-spinner fa-spin' : 'fas fa-paperclip'"></i>
      </button>

      <textarea 
        v-model="chatStore.userInput" 
        @keydown="handleKeyDown"
        @compositionstart="handleCompositionStart"
        @compositionend="handleCompositionEnd"
        @input="autoResize"
        @paste="handlePaste"
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
    <div class="footer-text">
      <span class="footer-disclaimer"><i class="fas fa-shield-halved"></i> NovaChat 可能产生不准确的信息，请核验重要内容。</span>
      <a class="icp-link" href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">赣ICP备2026017220号</a>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, nextTick } from 'vue';
import { useChatStore } from '@/stores/chat';
import type { MessageAttachment } from '@/types/chat';
import {
  DOCUMENT_EXTENSIONS,
  IMAGE_EXTENSIONS,
  fetchVisionCapability,
  isImageFile,
  uploadChatAttachment,
  validateFile,
} from '@/utils/attachments';

const chatStore = useChatStore();
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);
const isComposing = ref(false);

type AttachmentStatus = 'uploading' | 'ready' | 'failed';
interface PendingAttachment {
  key: string;
  file: File;
  preview: string | null;
  status: AttachmentStatus;
  // 上传成功后由后端返回，发送时只传 id
  uploaded?: MessageAttachment;
  error?: string;
}

const attachments = ref<PendingAttachment[]>([]);
const attachmentError = ref('');
// 当前模型是否支持图像理解，由后端能力接口决定
const visionEnabled = ref(true);
const ACCEPT_ATTR = computed(() =>
  (visionEnabled.value ? [...IMAGE_EXTENSIONS, ...DOCUMENT_EXTENSIONS] : DOCUMENT_EXTENSIONS).join(','),
);
const MAX_ATTACHMENTS = 6;
const quickPrompts = [
  '帮我总结核心内容',
  '解释得更简单一些',
  '列出关键步骤',
  '对比不同观点',
  '给我一个示例',
];

const isUploading = computed(() => attachments.value.some((item) => item.status === 'uploading'));
const readyAttachments = computed(() =>
  attachments.value
    .filter((item) => item.status === 'ready' && item.uploaded)
    .map((item) => item.uploaded as MessageAttachment),
);
const canSend = computed(() => {
  return !chatStore.isLoading && !chatStore.isInputLocked && !isUploading.value
    && (!!chatStore.userInput.trim() || readyAttachments.value.length > 0);
});

const fileIcon = (filename: string) => {
  const ext = filename.slice(filename.lastIndexOf('.')).toLowerCase();
  if (['.pdf'].includes(ext)) return 'fas fa-file-pdf';
  if (['.doc', '.docx'].includes(ext)) return 'fas fa-file-word';
  if (['.xls', '.xlsx'].includes(ext)) return 'fas fa-file-excel';
  return 'far fa-file-lines';
};

onMounted(async () => {
  visionEnabled.value = await fetchVisionCapability();
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

const revokePreview = (attachment: PendingAttachment) => {
  if (attachment.preview) URL.revokeObjectURL(attachment.preview);
};

// 必须从响应式数组里按 key 取回实例再改，直接改 push 前的原始对象不会触发视图更新
const uploadOne = async (key: string) => {
  const attachment = attachments.value.find((item) => item.key === key);
  if (!attachment) return;
  attachment.status = 'uploading';
  attachment.error = '';
  try {
    const uploaded = await uploadChatAttachment(attachment.file);
    const current = attachments.value.find((item) => item.key === key);
    if (!current) return;
    current.uploaded = {
      id: uploaded.id,
      filename: uploaded.filename,
      kind: uploaded.kind,
      mime: uploaded.mime,
    };
    current.status = 'ready';
  } catch (error: any) {
    const current = attachments.value.find((item) => item.key === key);
    if (!current) return;
    current.status = 'failed';
    current.error = error?.response?.data?.detail || error?.message || '上传失败';
    attachmentError.value = `${current.file.name}：${current.error}`;
  }
};

const addFiles = async (files: File[]) => {
  const accepted: PendingAttachment[] = [];
  for (const file of files) {
    if (attachments.value.length + accepted.length >= MAX_ATTACHMENTS) {
      attachmentError.value = `单条消息最多携带 ${MAX_ATTACHMENTS} 个附件`;
      break;
    }
    const duplicate = [...attachments.value, ...accepted].some(
      (item) => item.file.name === file.name && item.file.size === file.size,
    );
    if (duplicate) continue;

    if (!visionEnabled.value && isImageFile(file)) {
      attachmentError.value = `${file.name}：当前模型不支持图像理解，请上传文档`;
      continue;
    }
    const invalidReason = validateFile(file);
    if (invalidReason) {
      attachmentError.value = invalidReason;
      continue;
    }
    const key = `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2, 7)}`;
    accepted.push({
      key,
      file,
      preview: isImageFile(file) ? URL.createObjectURL(file) : null,
      status: 'uploading',
    });
  }
  if (!accepted.length) return;

  attachments.value.push(...accepted);
  await Promise.all(accepted.map((item) => uploadOne(item.key)));
};

const handleFiles = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  input.value = '';
  await addFiles(files);
};

// 支持直接从剪贴板粘贴图片
const handlePaste = async (event: ClipboardEvent) => {
  if (chatStore.isInputLocked) return;
  const files = Array.from(event.clipboardData?.files || []);
  const images = files.filter((file) => file.type.startsWith('image/'));
  if (!images.length) return;
  event.preventDefault();
  await addFiles(images);
};

const removeAttachment = (attachment: PendingAttachment) => {
  const index = attachments.value.findIndex((item) => item.key === attachment.key);
  if (index >= 0) attachments.value.splice(index, 1);
  revokePreview(attachment);
};

const clearAttachments = () => {
  attachments.value.forEach(revokePreview);
  attachments.value = [];
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

  const sending = readyAttachments.value;
  const sent = await chatStore.handleSend({ attachments: sending });
  if (!sent) return;

  clearAttachments();
  attachmentError.value = '';
  await nextTick();
  resetTextareaHeight();
};

onBeforeUnmount(() => {
  clearAttachments();
});
</script>
