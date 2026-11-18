<template>
  <div
    class="document-item" 
    :class="{ deleting: isDeleting }"
  >
    <div class="document-main">
      <div class="document-row">
        <div class="document-info">
          <div class="document-icon" :class="`file-${doc.file_type.toLowerCase()}`">
            <i :class="getFileIcon(doc.file_type)"></i>
          </div>
          <div class="document-details">
            <div class="document-name">{{ doc.filename }}</div>
            <div class="document-meta">
              <span class="document-type">{{ doc.file_type }}</span>
              <span class="document-chunks"><i class="fas fa-layer-group"></i>{{ doc.chunk_count }} 个文本片段</span>
            </div>
          </div>
        </div>
        <button
          type="button"
          @click="onDelete"
          class="document-delete-btn"
          :title="isDeleting ? '正在删除文档' : '删除文档'"
          :aria-label="isDeleting ? `正在删除 ${doc.filename}` : `删除 ${doc.filename}`"
          :disabled="isDeleting"
        >
          <i :class="isDeleting ? 'fas fa-spinner fa-spin' : 'fas fa-trash-can'"></i>
          <span>{{ isDeleting ? '删除中…' : '删除' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useDocumentStore } from '@/stores/documents';
import type { DocumentItem } from '@/types/document';

const props = defineProps<{
  doc: DocumentItem;
}>();

const documentStore = useDocumentStore();
const isDeleting = computed(() => documentStore.deletingDocuments.includes(props.doc.filename));

const getFileIcon = (fileType: string) => {
  if (fileType === 'PDF') {
    return 'fas fa-file-pdf';
  } else if (fileType === 'Word') {
    return 'fas fa-file-word';
  } else if (fileType === 'Excel') {
    return 'fas fa-file-excel';
  }
  return 'fas fa-file';
};

const onDelete = async () => {
  try {
    await documentStore.deleteDocument(props.doc.filename);
  } catch (error: any) {
    alert(error.message);
  }
};

</script>

<style scoped>
.document-type {
  padding: 3px 9px;
  border: 1px solid var(--nova-border);
  border-radius: 999px;
  background: var(--nova-surface-soft);
  color: var(--nova-text-secondary);
  font-size: 0.74rem;
  font-weight: 700;
}

.document-chunks {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--nova-text-secondary);
}

.document-chunks i {
  color: var(--nova-primary);
  font-size: 0.76rem;
}

.document-delete-btn {
  display: inline-flex;
  min-height: 40px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 13px;
  border: 1px solid color-mix(in srgb, var(--nova-danger) 28%, var(--nova-border));
  border-radius: 12px;
  background: color-mix(in srgb, var(--nova-danger) 8%, var(--nova-surface));
  color: var(--nova-danger);
  font: inherit;
  font-size: 0.84rem;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease;
}

.document-delete-btn:hover:not(:disabled) {
  border-color: var(--nova-danger);
  background: var(--nova-danger);
  color: var(--nova-surface);
}

.document-delete-btn:disabled {
  cursor: wait;
  opacity: 0.7;
}

.document-delete-btn:focus-visible {
  outline: 3px solid color-mix(in srgb, var(--nova-primary) 34%, transparent);
  outline-offset: 2px;
}

.deleting {
  opacity: 0.72;
}

@media (max-width: 520px) {
  .document-delete-btn {
    width: 40px;
    padding: 0;
  }

  .document-delete-btn span {
    display: none;
  }
}
</style>
