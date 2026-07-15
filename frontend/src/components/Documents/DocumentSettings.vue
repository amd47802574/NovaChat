<template>
  <div class="settings-panel">
    <div class="settings-header">
      <button class="settings-back-btn" type="button" title="返回对话" @click="backToChat">
        <i class="fas fa-arrow-left"></i>
      </button>
      <div>
        <h2><i class="fas fa-cog"></i> 文档管理</h2>
        <p>上传文档进行向量化处理，支持 PDF 和 Word、Excel 格式</p>
      </div>
    </div>

    <UploadSection />

    <div class="documents-section">
      <h3><i class="fas fa-list"></i> 已上传文档</h3>
      <button @click="onRefresh" class="btn-secondary" :disabled="documentStore.documentsLoading">
        <i class="fas fa-sync" :class="{ 'fa-spin': documentStore.documentsLoading }"></i> 刷新列表
      </button>
      
      <div v-if="documentStore.documentsLoading" class="loading-indicator">
        加载中...
      </div>
      
      <div v-else-if="documentStore.documents.length === 0" class="empty-documents">
        <i class="fas fa-inbox"></i>
        <p>暂无文档</p>
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
import { onMounted, onUnmounted } from 'vue';
import UploadSection from './UploadSection.vue';
import DocumentItem from './DocumentItem.vue';
import { useDocumentStore } from '@/stores/documents';
import { useChatStore } from '@/stores/chat';

const documentStore = useDocumentStore();
const chatStore = useChatStore();

const backToChat = () => {
  chatStore.activeNav = 'newChat';
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

onUnmounted(() => {
  // 上传轮询归属于上传任务本身，离开设置页时仅停止删除任务轮询
  documentStore.stopAllDeleteJobPolling();
});
</script>
