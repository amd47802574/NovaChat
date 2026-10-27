<template>
  <div v-if="list.length" class="msg-attachments">
    <button
      v-for="item in imageAttachments"
      :key="item.id"
      type="button"
      class="msg-attachment-thumb"
      :title="item.filename"
      @click="openPreview(item)"
    >
      <img v-if="urls[item.id]" :src="urls[item.id]" :alt="item.filename" />
      <span v-else-if="failed[item.id]" class="thumb-fallback">
        <i class="fas fa-image"></i>
      </span>
      <span v-else class="thumb-loading">
        <i class="fas fa-spinner fa-spin"></i>
      </span>
    </button>

    <button
      v-for="item in documentAttachments"
      :key="item.id"
      type="button"
      class="msg-attachment-file"
      :title="`下载 ${item.filename}`"
      @click="onDownload(item)"
    >
      <i :class="iconFor(item)"></i>
      <span class="file-name">{{ item.filename }}</span>
      <i class="fas fa-download file-action"></i>
    </button>
  </div>

  <Teleport to="body">
    <div v-if="previewUrl" class="msg-attachment-lightbox" @click="preview = null">
      <img :src="previewUrl" :alt="preview?.filename" />
      <div class="lightbox-caption">{{ preview?.filename }}</div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';
import type { MessageAttachment } from '@/types/chat';
import { downloadAttachment, extensionOf, getAttachmentBlobUrl } from '@/utils/attachments';

const props = defineProps<{
  attachments?: MessageAttachment[];
}>();

const urls = reactive<Record<string, string>>({});
const failed = reactive<Record<string, boolean>>({});
const preview = ref<MessageAttachment | null>(null);

const list = computed(() => props.attachments || []);
const imageAttachments = computed(() => list.value.filter((item) => item.kind === 'image'));
const documentAttachments = computed(() => list.value.filter((item) => item.kind !== 'image'));
const previewUrl = computed(() => (preview.value ? urls[preview.value.id] || '' : ''));

const DOC_ICONS: Record<string, string> = {
  '.pdf': 'fas fa-file-pdf',
  '.doc': 'fas fa-file-word',
  '.docx': 'fas fa-file-word',
  '.xls': 'fas fa-file-excel',
  '.xlsx': 'fas fa-file-excel',
  '.md': 'fas fa-file-lines',
  '.txt': 'fas fa-file-lines',
};

const iconFor = (item: MessageAttachment): string => {
  return DOC_ICONS[extensionOf(item.filename)] || 'fas fa-file-lines';
};

const loadImages = async () => {
  await Promise.all(
    imageAttachments.value.map(async (item) => {
      if (urls[item.id]) return;
      try {
        urls[item.id] = await getAttachmentBlobUrl(item.id);
      } catch (_) {
        failed[item.id] = true;
      }
    }),
  );
};

watch(() => props.attachments, loadImages, { immediate: true, deep: false });

const openPreview = (item: MessageAttachment) => {
  if (!urls[item.id]) return;
  preview.value = item;
};

const onDownload = async (item: MessageAttachment) => {
  try {
    await downloadAttachment(item.id, item.filename);
  } catch (error: any) {
    alert(`附件下载失败：${error?.response?.status === 404 ? '文件已过期或被清理' : error?.message || '未知错误'}`);
  }
};

onBeforeUnmount(() => {
  preview.value = null;
});
</script>
