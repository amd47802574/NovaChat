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
      <div class="upload-picker">
        <div class="upload-picker-icon"><i class="fas fa-arrow-up-from-bracket"></i></div>
        <div class="upload-picker-copy">
          <strong>选择文件，自动开始上传</strong>
          <span>支持 PDF、Word、Excel、HTML 和 Markdown，单个文件最大 30 MB</span>
        </div>
        <button type="button" @click="triggerFileSelect" class="upload-btn" :disabled="documentStore.isUploading">
          <i class="fas fa-folder-open"></i> 选择文档
        </button>
      </div>

      <div v-if="documentStore.selectedFile" class="selected-file" :class="{ failed: uploadFailed }">
        <div class="selected-file-icon"><i :class="getSelectedFileIcon"></i></div>
        <div class="selected-file-details">
          <strong class="selected-file-name" :title="documentStore.selectedFile.name">
            {{ documentStore.selectedFile.name }}
          </strong>
          <span>{{ selectedFileStatus }}</span>
        </div>
        <i
          class="selected-file-status-icon"
          :class="documentStore.isUploading ? 'fas fa-circle-notch fa-spin' : uploadFailed ? 'fas fa-circle-exclamation' : 'fas fa-circle-check'"
          aria-hidden="true"
        ></i>
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
import { computed, ref } from 'vue';
import { useDocumentStore } from '@/stores/documents';

const documentStore = useDocumentStore();
const fileInputRef = ref<HTMLInputElement | null>(null);

// 与后端 MAX_DOCUMENT_SIZE_MB 保持一致（backend/api/resources.py）
const MAX_DOCUMENT_SIZE_MB = 30;
const uploadFailed = computed(() => documentStore.uploadSteps.some((step) => step.status === 'failed'));
const selectedFileStatus = computed(() => {
  if (documentStore.isUploading) return documentStore.uploadProgress || '正在上传并处理…';
  if (uploadFailed.value) return '处理失败，请重新选择文件重试';
  return '已加入知识库';
});
const getSelectedFileIcon = computed(() => {
  const fileType = documentStore.selectedFile?.name.split('.').pop()?.toLowerCase();
  if (fileType === 'pdf') return 'fas fa-file-pdf';
  if (['doc', 'docx'].includes(fileType || '')) return 'fas fa-file-word';
  if (['xls', 'xlsx'].includes(fileType || '')) return 'fas fa-file-excel';
  return 'fas fa-file-lines';
});

const triggerFileSelect = () => {
  fileInputRef.value?.click();
};

const onFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (file) {
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
    void onUpload();
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

.upload-format {
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

.upload-picker {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px;
  border: 1px dashed color-mix(in srgb, var(--nova-primary) 42%, var(--nova-border));
  border-radius: 16px;
  background: color-mix(in srgb, var(--nova-primary) 4%, var(--nova-surface));
}

.upload-picker-icon,
.selected-file-icon {
  display: grid;
  width: 46px;
  height: 46px;
  flex: 0 0 46px;
  place-items: center;
  border-radius: 14px;
  background: color-mix(in srgb, var(--nova-primary) 12%, var(--nova-surface));
  color: var(--nova-primary);
  font-size: 1.1rem;
}

.upload-picker-copy,
.selected-file-details {
  display: flex;
  min-width: 0;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 5px;
}

.upload-picker-copy strong {
  color: var(--nova-text);
  font-size: 0.92rem;
}

.upload-picker-copy span {
  display: block;
  color: var(--nova-text-secondary);
  font-size: 0.78rem;
  line-height: 1.45;
}

.upload-picker .upload-btn {
  min-height: 42px;
  flex: 0 0 auto;
  padding: 0 18px;
  border-radius: 12px;
}

.upload-picker .upload-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
  transform: none;
}

.selected-file {
  display: flex;
  align-items: center;
  gap: 13px;
  min-height: 72px;
  min-width: 0;
  padding: 12px 15px;
  border: 1px solid var(--nova-border);
  border-radius: 14px;
  background: var(--nova-surface);
}

.selected-file-icon {
  width: 40px;
  height: 40px;
  flex-basis: 40px;
  background: var(--nova-surface-soft);
  font-size: 1rem;
}

.selected-file-name {
  overflow: hidden;
  color: var(--nova-text);
  font-size: 0.86rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.selected-file-details span {
  overflow: hidden;
  color: var(--nova-text-secondary);
  font-size: 0.76rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.selected-file-status-icon {
  flex: 0 0 auto;
  color: var(--nova-primary);
}

.selected-file.failed .selected-file-status-icon {
  color: var(--nova-danger);
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

  .upload-picker {
    align-items: flex-start;
    flex-direction: column;
  }

  .upload-picker .upload-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
