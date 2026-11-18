import { defineStore } from 'pinia';
import api from '@/utils/api';
import type { DocumentItem, UploadStep } from '@/types/document';

export const useDocumentStore = defineStore('documents', {
  state: () => ({
    documents: [] as DocumentItem[],
    documentsLoading: false,
    selectedFile: null as File | null,
    isUploading: false,
    uploadProgress: '',
    uploadSteps: [] as UploadStep[],
    uploadProgressCollapsed: false,
    activeUploadJobId: '',
    uploadPollTimer: null as any,
    deletingDocuments: [] as string[],
  }),

  actions: {
    createUploadSteps(): UploadStep[] {
      return [
        { key: 'upload', label: '文档上传', percent: 0, status: 'pending', message: '' },
        { key: 'cleanup', label: '清理旧版本', percent: 0, status: 'pending', message: '' },
        { key: 'parse', label: '解析与分块', percent: 0, status: 'pending', message: '' },
        { key: 'parent_store', label: '父级分块入库', percent: 0, status: 'pending', message: '' },
        { key: 'vector_store', label: '向量化入库', percent: 0, status: 'pending', message: '' },
      ];
    },

    updateUploadStep(key: string, percent: number, status: UploadStep['status'] = 'running', message = '') {
      if (!this.uploadSteps.length) {
        this.uploadSteps = this.createUploadSteps();
      }
      const idx = this.uploadSteps.findIndex((step) => step.key === key);
      if (idx === -1) return;
      this.uploadSteps[idx] = {
        ...this.uploadSteps[idx],
        percent: Math.max(0, Math.min(100, Math.round(percent || 0))),
        status,
        message,
      };
    },

    async loadDocuments() {
      this.documentsLoading = true;
      try {
        const response = await api.get('/documents');
        this.documents = (response.data.documents || []).filter(
          (doc: DocumentItem) => !this.deletingDocuments.includes(doc.filename)
        );
      } catch (error: any) {
        const errMsg = error.response?.data?.detail || error.message || '加载文档列表失败';
        throw new Error(errMsg);
      } finally {
        this.documentsLoading = false;
      }
    },

    // 上传任务完成后，向量库写入与列表查询之间可能存在短暂延迟，
    // 这里轮询列表直到新文件可见，避免用户必须手动刷新页面。
    async refreshDocumentsUntilVisible(filename: string, attempts = 6, intervalMs = 1000) {
      for (let attempt = 0; attempt < attempts; attempt += 1) {
        try {
          await this.loadDocuments();
          if (!filename || this.documents.some((doc) => doc.filename === filename)) {
            return;
          }
        } catch {
          // 列表查询偶发失败时继续重试，避免整个刷新流程中断
        }
        if (attempt < attempts - 1) {
          await new Promise((resolve) => setTimeout(resolve, intervalMs));
        }
      }
      // 重试耗尽后兜底再拉一次，失败也交由调用方忽略
      try {
        await this.loadDocuments();
      } catch {
        // 忽略：保留当前列表
      }
    },

    async uploadDocument() {
      if (!this.selectedFile) {
        throw new Error('请先选择文件');
      }

      this.isUploading = true;
      this.uploadProgress = '正在上传...';
      this.uploadSteps = this.createUploadSteps();
      this.uploadProgressCollapsed = false;
      this.updateUploadStep('upload', 0, 'running', '准备上传');

      const formData = new FormData();
      formData.append('file', this.selectedFile);

      try {
        const response = await api.post('/documents/upload/async', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          onUploadProgress: (progressEvent) => {
            if (!progressEvent.total) return;
            const percent = Math.round((progressEvent.loaded / progressEvent.total) * 100);
            this.updateUploadStep('upload', percent, 'running', `已上传 ${percent}%`);
          },
        });

        const data = response.data;
        this.updateUploadStep('upload', 100, 'completed', '文档上传完成');
        this.uploadProgress = data.message;
        this.activeUploadJobId = data.job_id;
        this.startUploadJobPolling(data.job_id);
      } catch (error: any) {
        const errMsg = error.response?.data?.detail || error.message || '上传失败';
        this.updateUploadStep('upload', 100, 'failed', errMsg);
        this.uploadProgress = '上传失败：' + errMsg;
        this.isUploading = false;
        throw new Error(errMsg);
      }
    },

    syncUploadJob(job: any) {
      this.activeUploadJobId = job.job_id;
      // 上传成功后不再展示流程面板，直接清空进度状态
      if (job.status === 'completed') {
        this.uploadSteps = [];
        this.uploadProgress = '';
        this.uploadProgressCollapsed = false;
        return;
      }
      this.uploadProgress = job.message || '';
      if (Array.isArray(job.steps)) {
        this.uploadSteps = job.steps.map((step: any) => ({
          key: step.key,
          label: step.label,
          percent: step.percent,
          status: step.status,
          message: step.message || '',
        }));
      }
    },

    startUploadJobPolling(jobId: string) {
      this.stopUploadJobPolling();

      let consecutiveErrors = 0;
      const poll = async () => {
        try {
          const response = await api.get(`/documents/upload/jobs/${encodeURIComponent(jobId)}`);
          const job = response.data;
          consecutiveErrors = 0;
          this.syncUploadJob(job);

          if (job.status === 'completed') {
            this.stopUploadJobPolling();
            this.isUploading = false;
            this.selectedFile = null;
            await this.refreshDocumentsUntilVisible(job.filename || '');
          } else if (job.status === 'failed') {
            this.stopUploadJobPolling();
            this.isUploading = false;
          }
        } catch (error: any) {
          // 偶发的网络抖动或后端繁忙不应中断轮询，连续失败后才放弃
          consecutiveErrors += 1;
          if (consecutiveErrors < 3) {
            this.uploadProgress = '进度查询重试中...';
            return;
          }
          this.uploadProgress = '进度查询失败：' + (error.response?.data?.detail || error.message);
          this.stopUploadJobPolling();
          this.isUploading = false;
        }
      };

      poll();
      this.uploadPollTimer = setInterval(poll, 1000);
    },

    stopUploadJobPolling() {
      if (this.uploadPollTimer) {
        clearInterval(this.uploadPollTimer);
        this.uploadPollTimer = null;
      }
    },

    async deleteDocument(filename: string) {
      if (this.deletingDocuments.includes(filename)) return;
      if (!confirm(`确定要删除知识库文档“${filename}”吗？相关向量和父级分块也会一并删除。`)) return;

      this.deletingDocuments = [...this.deletingDocuments, filename];
      try {
        await api.delete(`/documents/${encodeURIComponent(filename)}`);
        this.documents = this.documents.filter((doc) => doc.filename !== filename);
      } catch (error: any) {
        const errMsg = error.response?.data?.detail || error.message || '删除失败';
        throw new Error(errMsg);
      } finally {
        this.deletingDocuments = this.deletingDocuments.filter((item) => item !== filename);
      }
    },
  },
});
export type { DocumentItem };
