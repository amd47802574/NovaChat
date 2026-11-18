<template>
  <div class="settings-panel">
    <div class="settings-header">
      <button v-if="!embedded" class="settings-back-btn" type="button" title="返回对话" @click="backToChat">
        <i class="fas fa-arrow-left"></i>
      </button>
      <div>
        <h2><i class="fas fa-cog"></i> 知识库文档管理</h2>
        <p>集中管理知识库资料，上传后自动解析并建立检索索引。</p>
      </div>
      <div class="settings-summary" aria-label="知识库概览">
        <div class="summary-stat">
          <strong>{{ documentStore.documents.length }}</strong>
          <span>份文档</span>
        </div>
        <div class="summary-stat">
          <strong>{{ totalChunks.toLocaleString() }}</strong>
          <span>个文本片段</span>
        </div>
      </div>
    </div>

    <UploadSection />

    <div class="documents-section">
      <div class="documents-heading">
        <div>
          <h3><i class="fas fa-folder-open"></i> 知识库文档</h3>
          <p>管理已入库的资料与检索片段</p>
        </div>
        <button type="button" @click="onRefresh" class="btn-secondary refresh-documents-btn" :disabled="documentStore.documentsLoading">
          <i class="fas fa-rotate" :class="{ 'fa-spin': documentStore.documentsLoading }"></i>
          {{ documentStore.documentsLoading ? '正在刷新' : '刷新列表' }}
        </button>
      </div>
      
      <div v-if="documentStore.documentsLoading && !documentStore.documents.length" class="loading-indicator">
        <i class="fas fa-circle-notch fa-spin"></i>
        <span>正在加载文档…</span>
      </div>
      
      <div v-else-if="documentStore.documents.length === 0" class="empty-documents">
        <div class="empty-documents-icon"><i class="fas fa-box-open"></i></div>
        <strong>知识库还是空的</strong>
        <p>上传 PDF、Word、Excel 或 Markdown 文档，开始构建可检索的知识库。</p>
      </div>
      
      <div v-else class="documents-list">
        <DocumentItem 
          v-for="doc in documentStore.documents" 
          :key="doc.filename" 
          :doc="doc" 
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';
import UploadSection from './UploadSection.vue';
import DocumentItem from './DocumentItem.vue';
import { useDocumentStore } from '@/stores/documents';
import { useChatStore } from '@/stores/chat';

// embedded=true 时作为超级管理员后台「文档管理」Tab 内嵌，隐藏「返回对话」按钮。
const props = withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false });

const documentStore = useDocumentStore();
const chatStore = useChatStore();
const totalChunks = computed(() => documentStore.documents.reduce((total, doc) => total + doc.chunk_count, 0));

const backToChat = () => {
  chatStore.setActiveNav('newChat');
};

const onRefresh = async () => {
  try {
    await documentStore.loadDocuments();
  } catch (error: any) {
    alert(error.message);
  }
};

onMounted(() => {
  documentStore.loadDocuments();
});
</script>

<style scoped>
.settings-panel {
  padding: clamp(18px, 3vw, 34px);
}

.settings-header {
  align-items: center;
  gap: 18px;
  margin-bottom: 22px;
  padding: 0 0 22px;
  border-bottom: 1px solid var(--nova-border);
}

.settings-header > div:first-of-type {
  min-width: 0;
  flex: 1 1 auto;
}

.settings-header h2 {
  margin: 0;
  font-size: clamp(1.35rem, 2.2vw, 1.8rem);
  letter-spacing: -0.025em;
}

.settings-header p {
  margin-top: 7px;
  line-height: 1.55;
}

.settings-summary {
  display: flex;
  flex: 0 0 auto;
  gap: 10px;
}

.summary-stat {
  display: flex;
  min-width: 104px;
  flex-direction: column;
  gap: 3px;
  padding: 11px 14px;
  border: 1px solid var(--nova-border);
  border-radius: 14px;
  background: var(--nova-surface);
}

.summary-stat strong {
  color: var(--nova-text);
  font-size: 1.15rem;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

.summary-stat span {
  color: var(--nova-text-secondary);
  font-size: 0.75rem;
}

.documents-section {
  padding: clamp(18px, 2.6vw, 26px);
}

.documents-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.documents-heading h3 {
  margin: 0;
  font-size: 1.08rem;
}

.documents-heading p {
  margin-top: 5px;
  color: var(--nova-text-secondary);
  font-size: 0.84rem;
}

.refresh-documents-btn {
  margin: 0;
  border: 1px solid var(--nova-border);
  background: var(--nova-surface);
  color: var(--nova-text-secondary);
}

.refresh-documents-btn:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--nova-primary) 44%, var(--nova-border));
  background: var(--nova-surface-soft);
  color: var(--nova-primary);
  transform: none;
}

.loading-indicator {
  display: flex;
  min-height: 160px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--nova-text-secondary);
}

.loading-indicator i {
  color: var(--nova-primary);
}

.empty-documents {
  display: flex;
  min-height: 230px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 26px;
  color: var(--nova-text-secondary);
}

.empty-documents-icon {
  display: grid;
  width: 58px;
  height: 58px;
  margin-bottom: 4px;
  place-items: center;
  border-radius: 18px;
  background: color-mix(in srgb, var(--nova-primary) 10%, var(--nova-surface));
  color: var(--nova-primary);
  font-size: 1.35rem;
}

.empty-documents strong {
  color: var(--nova-text);
  font-size: 0.98rem;
}

.empty-documents p {
  max-width: 400px;
  margin: 0;
  font-size: 0.86rem;
  line-height: 1.55;
  text-align: center;
}

.documents-list {
  gap: 9px;
}

@media (max-width: 640px) {
  .settings-header {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .settings-summary {
    width: 100%;
  }

  .summary-stat {
    min-width: 0;
    flex: 1;
  }

  .documents-heading {
    align-items: flex-start;
  }
}

@media (max-width: 420px) {
  .documents-heading {
    flex-direction: column;
  }

  .refresh-documents-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
