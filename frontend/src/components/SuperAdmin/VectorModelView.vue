<template>
  <div class="vector-page">
    <div class="title-row">
      <div>
        <h3><i class="fas fa-cubes"></i> 向量与重排模型</h3>
        <p>管理知识库向量生成和召回后的相关性排序。</p>
      </div>
      <div class="toolbar">
        <span v-if="store.vectorConfigAppliedAt" class="applied-tag">
          <i class="fas fa-check-circle"></i> 已生效：{{ formatTime(store.vectorConfigAppliedAt) }}
        </span>
        <button class="save-btn" :disabled="busy || store.vectorConfigLoading" @click="save">
          <i class="fas fa-save"></i> {{ busy ? '处理中…' : '保存并应用' }}
        </button>
      </div>
    </div>

    <div class="notice">
      <i class="fas fa-shield-halved"></i>
      更换向量模型会在新 Milvus 集合中重新处理服务器保存的全部知识库文档。迁移成功后才会切换，旧集合会保留；
      若文档原文件缺失或迁移失败，当前配置和知识库仍保持不变。
    </div>

    <div v-if="store.vectorConfigLoading && !store.vectorConfig.length" class="card loading">正在读取配置…</div>
    <template v-else>
      <section class="card">
        <header><span class="step">01</span><div><h4>稠密向量模型</h4><p>为知识库文档和用户问题生成向量。</p></div></header>
        <label>服务商</label>
        <select v-model="form.EMBEDDING_PROVIDER" :disabled="busy" @change="onEmbeddingProviderChange">
          <option value="huggingface">本地 Sentence Transformers</option>
          <option value="dashscope">阿里云百炼</option>
        </select>
        <label>模型名称</label>
        <input v-model.trim="form.EMBEDDING_MODEL" :disabled="busy" :placeholder="form.EMBEDDING_PROVIDER === 'dashscope' ? 'qwen3.7-text-embedding-flash' : 'sentence-transformers/all-MiniLM-L6-v2'" @change="normalizeEmbeddingConfig" />
        <div class="form-grid">
          <div>
            <label>向量维度</label>
            <select v-model="form.DENSE_EMBEDDING_DIM" :disabled="busy || form.EMBEDDING_PROVIDER === 'dashscope'">
              <option v-for="dim in dimensions" :key="dim" :value="String(dim)">{{ dim }}</option>
            </select>
          </div>
          <div v-if="form.EMBEDDING_PROVIDER === 'huggingface'">
            <label>运行设备</label>
            <select v-model="form.EMBEDDING_DEVICE" :disabled="busy">
              <option value="cpu">CPU</option><option value="cuda">CUDA</option>
            </select>
          </div>
        </div>
        <template v-if="form.EMBEDDING_PROVIDER === 'dashscope' || form.RERANK_PROVIDER === 'dashscope'">
          <label>Base URL</label>
          <input v-model.trim="form.DASHSCOPE_EMBEDDING_URL" :disabled="busy" placeholder="https://llm-<workspace>.cn-beijing.maas.aliyuncs.com/compatible-mode/v1" />
          <small v-if="form.EMBEDDING_PROVIDER === 'dashscope'">Embedding 使用此 Base URL + /embeddings；qwen3.7-text-embedding-flash 固定返回 1024 维。</small>
          <small v-if="form.RERANK_PROVIDER === 'dashscope'">百炼 Rerank 使用此 Base URL，并在重排模型区域单独配置 API Key。</small>
        </template>
        <template v-if="form.EMBEDDING_PROVIDER === 'dashscope'">
          <SecretKeyField
            v-model="form.DASHSCOPE_API_KEY"
            label="API Key"
            :is-set="isSet('DASHSCOPE_API_KEY')"
            :disabled="busy"
            description="百炼 Embedding 服务的 API Key，用于生成知识库向量；留空表示沿用当前密钥。"
          />
        </template>
      </section>

      <section class="card">
        <header><span class="step">02</span><div><h4>重排模型</h4><p>对向量与 BM25 初步召回的候选片段重新排序。</p></div></header>
        <label>服务商</label>
        <select v-model="form.RERANK_PROVIDER" :disabled="busy" @change="onRerankProviderChange">
          <option value="custom">硅基流动</option>
          <option value="dashscope">阿里云百炼</option>
        </select>
        <label>模型名称</label>
        <input v-model.trim="form.RERANK_MODEL" :disabled="busy" :placeholder="form.RERANK_PROVIDER === 'dashscope' ? 'qwen3.7-text-rerank' : 'BAAI/bge-reranker-v2-m3'" />
        <template v-if="form.RERANK_PROVIDER === 'custom'">
          <label>Base URL</label>
          <input v-model.trim="form.RERANK_BINDING_HOST" :disabled="busy" placeholder="https://api.example.com/v1" />
          <SecretKeyField
            v-model="form.RERANK_API_KEY"
            label="API Key"
            :is-set="isSet('RERANK_API_KEY')"
            :disabled="busy"
            placeholder="请输入硅基流动 API Key"
            description="硅基流动 Rerank 服务的 API Key，用于接口身份认证；留空表示沿用当前密钥。"
          />
        </template>
        <template v-else>
          <SecretKeyField
            v-model="form.DASHSCOPE_RERANK_API_KEY"
            label="API Key"
            :is-set="isSet('DASHSCOPE_RERANK_API_KEY')"
            :disabled="busy"
            placeholder="请输入百炼 Rerank API Key"
            description="百炼 Rerank 服务的 API Key，用于接口身份认证；留空保留已保存密钥，未单独配置时沿用 Embedding API Key。"
          />
        </template>
      </section>

      <section v-if="store.vectorMigrationJob" class="card job-card" :class="store.vectorMigrationJob.status">
        <h4><i class="fas fa-arrows-rotate"></i> 向量迁移任务</h4>
        <p>{{ store.vectorMigrationJob.message }}</p>
        <div v-if="store.vectorMigrationJob.status === 'running' && store.vectorMigrationJob.total_files" class="progress-track">
          <span :style="{ width: `${Math.round(store.vectorMigrationJob.processed_files * 100 / store.vectorMigrationJob.total_files)}%` }"></span>
        </div>
        <small v-if="store.vectorMigrationJob.total_files">{{ store.vectorMigrationJob.processed_files }} / {{ store.vectorMigrationJob.total_files }} 个文档</small>
      </section>

      <div v-if="feedback" class="feedback" :class="feedbackType">{{ feedback }}</div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue';
import { useSuperAdminStore } from '@/stores/superAdmin';
import type { UpdateVectorConfigRequest, VectorConfigField } from '@/types/user';
import { formatUtc8 } from '@/utils/time';
import SecretKeyField from './SecretKeyField.vue';

const store = useSuperAdminStore();
const dimensions = [256, 384, 512, 768, 1024];
const form = reactive<Record<string, string>>({});
const busy = ref(false);
const feedback = ref('');
const feedbackType = ref<'success' | 'error'>('success');
let pollTimer: ReturnType<typeof setInterval> | undefined;

const formatTime = (iso: string) => formatUtc8(iso, { withSeconds: true });

const isSet = (key: string) => store.vectorConfig.find((item) => item.key === key)?.is_set ?? false;

const normalizeEmbeddingConfig = () => {
  if (form.EMBEDDING_PROVIDER === 'dashscope') {
    form.DENSE_EMBEDDING_DIM = '1024';
  } else if (form.EMBEDDING_PROVIDER === 'huggingface' && form.EMBEDDING_MODEL === 'sentence-transformers/all-MiniLM-L6-v2') {
    form.DENSE_EMBEDDING_DIM = '384';
  }
};

const onEmbeddingProviderChange = () => {
  if (form.EMBEDDING_PROVIDER === 'huggingface') {
    form.EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2';
    form.DENSE_EMBEDDING_DIM = '384';
  } else {
    form.EMBEDDING_MODEL = 'qwen3.7-text-embedding-flash';
    form.DENSE_EMBEDDING_DIM = '1024';
  }
};

const onRerankProviderChange = () => {
  form.RERANK_MODEL = form.RERANK_PROVIDER === 'dashscope'
    ? 'qwen3.7-text-rerank'
    : 'BAAI/bge-reranker-v2-m3';
};

const hydrate = (fields: VectorConfigField[]) => {
  fields.forEach((field) => {
    form[field.key] = field.is_secret ? '' : field.value;
  });
};

const payload = (): UpdateVectorConfigRequest => {
  const result: Record<string, string> = {};
  store.vectorConfig.forEach((field) => {
    const value = (form[field.key] || '').trim();
    if (field.is_secret) {
      if (value) result[field.key.toLowerCase()] = value;
    } else if (value !== field.value) {
      result[field.key.toLowerCase()] = value;
    }
  });
  return result as UpdateVectorConfigRequest;
};

const watchJob = (jobId: string) => {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const job = await store.fetchVectorMigrationJob(jobId);
      if (job.status !== 'running') {
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = undefined;
        hydrate(store.vectorConfig);
        feedbackType.value = job.status === 'completed' ? 'success' : 'error';
        feedback.value = job.message;
        busy.value = false;
      }
    } catch (error: any) {
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = undefined;
      feedbackType.value = 'error';
      feedback.value = error?.message || '读取迁移状态失败';
      busy.value = false;
    }
  }, 2000);
};

const save = async () => {
  feedback.value = '';
  if (!form.EMBEDDING_MODEL?.trim() || !form.RERANK_MODEL?.trim()) {
    feedbackType.value = 'error';
    feedback.value = '向量模型和重排模型名称不能为空';
    return;
  }
  if (form.EMBEDDING_PROVIDER === 'dashscope' && Number(form.DENSE_EMBEDDING_DIM) !== 1024) {
    feedbackType.value = 'error';
    feedback.value = 'qwen3.7-text-embedding-flash 兼容模式固定为 1024 维';
    return;
  }
  busy.value = true;
  try {
    const result = await store.updateVectorConfig(payload());
    feedback.value = result.message;
    feedbackType.value = 'success';
    if (result.migration_job_id) {
      watchJob(result.migration_job_id);
    } else {
      hydrate(store.vectorConfig);
      busy.value = false;
    }
  } catch (error: any) {
    feedbackType.value = 'error';
    feedback.value = error?.message || '保存失败';
    busy.value = false;
  }
};

onMounted(async () => {
  try {
    await store.fetchVectorConfig();
    hydrate(store.vectorConfig);
  } catch (error: any) {
    feedbackType.value = 'error';
    feedback.value = error?.message || '读取配置失败';
  }
});

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer);
});
</script>

<style scoped>
.vector-page { display: flex; flex-direction: column; gap: 16px; }
.title-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.title-row h3 { color: var(--primary-color); font-size: 1.2rem; }
.title-row p, .card header p { margin-top: 4px; color: var(--text-light); font-size: .84rem; }
.toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.applied-tag { font-size: .8rem; color: #1f7a46; background: #e7f6ec; padding: 4px 10px; border-radius: 12px; white-space: nowrap; }
.save-btn { border: 0; border-radius: 12px; padding: 10px 18px; color: #fff; background: var(--primary-color); font-weight: 700; cursor: pointer; }
.save-btn:disabled { opacity: .6; cursor: default; }
.notice { padding: 12px 14px; border: 1px solid #f0d79c; border-radius: 12px; background: #fff9e9; color: #765814; line-height: 1.6; font-size: .86rem; }
.card { padding: 18px; border: 1px solid var(--border-color); border-radius: 14px; background: var(--white); box-shadow: var(--shadow); }
.card header { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; }
.card header h4, .job-card h4 { color: var(--text-color); }
.step { display: grid; place-items: center; width: 34px; height: 34px; flex: 0 0 auto; border-radius: 50%; background: #e8f1ff; color: var(--primary-color); font-weight: 800; }
.card label { display: block; margin: 14px 0 6px; font-size: .86rem; font-weight: 700; color: var(--text-color); }
.card input, .card select { width: 100%; min-height: 40px; box-sizing: border-box; border: 1px solid var(--border-color); border-radius: 10px; padding: 9px 11px; color: var(--text-color); background: #fff; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.secret { margin-left: 6px; color: #b54735; font-size: .72rem; }
.provider-note { margin-top: 14px; color: var(--text-light); font-size: .84rem; line-height: 1.55; }
.card small { display: block; margin-top: 8px; color: var(--text-light); }
.job-card.running { border-color: #93c5fd; }
.job-card.completed { border-color: #86c79c; }
.job-card.failed { border-color: #e7a19a; }
.job-card p { margin-top: 8px; color: var(--text-light); line-height: 1.5; overflow-wrap: anywhere; }
.progress-track { height: 8px; margin-top: 14px; overflow: hidden; border-radius: 10px; background: #e8edf4; }
.progress-track span { display: block; height: 100%; background: var(--primary-color); transition: width .25s ease; }
.feedback { padding: 12px 14px; border-radius: 12px; font-weight: 600; }
.feedback.success { background: #e7f6ec; color: #1f7a46; }
.feedback.error { background: #fdeceb; color: #c0392b; }
.loading { padding: 32px; text-align: center; color: var(--text-light); }
@media (max-width: 600px) { .form-grid { grid-template-columns: 1fr; gap: 0; } .toolbar, .save-btn { width: 100%; } .applied-tag { text-align: center; } }
</style>
