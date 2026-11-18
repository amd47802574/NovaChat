<template>
  <div class="upload-section">
    <div class="upload-heading">
      <div>
        <h3><i class="fas fa-cloud-arrow-up"></i> 添加知识库文档</h3>
        <p>文件会自动解析、切分并生成检索索引。</p>
      </div>
      <span class="upload-format"><i class="fas fa-file-circle-check"></i> PDF · Word · Excel · Markdown</span>
    </div>
    <div class="upload-area">
      <input 
        type="file" 
        ref="fileInputRef" 
        @change="onFileSelect"
        accept=".pdf,.doc,.docx,.xls,.xlsx,.html,.htm,.md,.markdown"
        style="display: none"
      />
      <div class="upload-actions">
        <button type="button" @click="triggerFileSelect" class="upload-btn" :disabled="documentStore.isUploading">
          <i class="fas fa-folder-open"></i> 选择文件
        </button>
        <span class="upload-limit">单个文件最大 30 MB</span>
      </div>
      
      <div v-if="documentStore.selectedFile" class="selected-file">
        <i class="fas fa-file"></i>
        <span class="selected-file-name" :title="documentStore.selectedFile.name">
          {{ documentStore.selectedFile.name }}
        </span>
        <button @click="onUpload" class="btn-primary" :disabled="documentStore.isUploading">
          <i class="fas fa-upload"></i> {{ documentStore.isUploading ? '上传中...' : '开始上传' }}
        </button>
      </div>

      <div v-if="documentStore.uploadSteps.length" class="upload-progress" :class="{ collapsed: documentStore.uploadProgressCollapsed }">
        <button type="button" class="upload-progress-header" @click="onToggleCollapse">
          <span v-if="documentStore.uploadProgress" class="upload-message">{{ documentStore.uploadProgress }}</span>
          <span v-else class="upload-message">上传进度</span>
          <span class="upload-toggle">{{ documentStore.uploadProgressCollapsed ? '展开' : '收起' }}</span>
        </button>
        
        <div v-show="!documentStore.uploadProgressCollapsed" class="upload-step-list">
          <div
            v-for="step in documentStore.uploadSteps"
            :key="step.key"
            class="upload-step"
            :class="`upload-step-${step.status}`"
          >
            <div class="upload-step-header">
              <span class="upload-step-label">{{ step.label }}</span>
              <span class="upload-step-percent">{{ step.percent }}%</span>
            </div>
            <div class="upload-step-bar">
              <div class="upload-step-fill" :style="{ width: step.percent + '%' }"></div>
            </div>
            <div v-if="step.message" class="upload-step-message">{{ step.message }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useDocumentStore } from '@/stores/documents';

const documentStore = useDocumentStore();
const fileInputRef = ref<HTMLInputElement | null>(null);

// 与后端 MAX_DOCUMENT_SIZE_MB 保持一致（backend/api/resources.py）
const MAX_DOCUMENT_SIZE_MB = 30;

const triggerFileSelect = () => {
  fileInputRef.value?.click();
};

const onFileSelect = (event: Event) => {
  const files = (event.target as HTMLInputElement).files;
  if (files && files.length > 0) {
    const file = files[0];
    if (file.size > MAX_DOCUMENT_SIZE_MB * 1024 * 1024) {
      alert(`文件过大：${(file.size / 1024 / 1024).toFixed(1)}MB，最大支持 ${MAX_DOCUMENT_SIZE_MB}MB`);
      (event.target as HTMLInputElement).value = '';
      return;
    }
    documentStore.selectedFile = file;
    documentStore.uploadProgress = '';
    documentStore.uploadSteps = [];
    documentStore.uploadProgressCollapsed = false;
    documentStore.activeUploadJobId = '';
  }
};

const onUpload = async () => {
  try {
    await documentStore.uploadDocument();
  } catch (error: any) {
    alert('上传文档失败: ' + error.message);
  }
};

const onToggleCollapse = () => {
  documentStore.uploadProgressCollapsed = !documentStore.uploadProgressCollapsed;
};
</script>

<style scoped>
.upload-section {
  padding: clamp(18px, 2.6vw, 26px);
}

.upload-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.upload-heading h3 {
  margin: 0;
  font-size: 1.08rem;
}

.upload-heading p {
  margin-top: 5px;
  color: var(--nova-text-secondary);
  font-size: 0.84rem;
}

.upload-format,
.upload-limit {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--nova-text-secondary);
  font-size: 0.8rem;
}

.upload-format {
  padding: 8px 11px;
  border: 1px solid var(--nova-border);
  border-radius: 999px;
  background: var(--nova-surface);
  white-space: nowrap;
}

.upload-format i {
  color: var(--nova-primary);
}

.upload-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.upload-actions .upload-btn {
  min-height: 42px;
  padding: 0 18px;
  border-radius: 12px;
}

.upload-actions .upload-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
  transform: none;
}

.selected-file {
  min-width: 0;
  border: 1px solid var(--nova-border);
  border-radius: 14px;
  background: var(--nova-surface-soft);
}

.selected-file .btn-primary {
  min-height: 40px;
  justify-content: center;
  border-radius: 11px;
}

@media (max-width: 640px) {
  .upload-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .upload-format {
    max-width: 100%;
    flex-wrap: wrap;
    border-radius: 12px;
    white-space: normal;
  }

  .upload-actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .upload-actions .upload-btn {
    width: 100%;
    justify-content: center;
  }

  .selected-file {
    flex-wrap: wrap;
  }

  .selected-file .selected-file-name {
    flex: 1 1 calc(100% - 50px);
  }

  .selected-file .btn-primary {
    width: 100%;
  }
}
</style>
