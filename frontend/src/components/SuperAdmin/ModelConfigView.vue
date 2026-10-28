<template>
  <div class="model-config">
    <div class="section-title">
      <h3><i class="fas fa-sliders"></i> 模型配置</h3>
      <div class="toolbar">
        <span v-if="store.modelConfigAppliedAt" class="applied-tag">
          <i class="fas fa-check-circle"></i> 已生效：{{ formatTime(store.modelConfigAppliedAt) }}
        </span>
        <button class="btn-secondary" :disabled="loading" @click="onReset">
          <i class="fas fa-undo"></i> 还原
        </button>
        <button class="btn-primary" :disabled="loading" @click="onSave">
          <i class="fas fa-save"></i> {{ loading ? '保存中...' : '保存并生效' }}
        </button>
      </div>
    </div>

    <p class="hint">
      以下配置存储于服务端 <code>.env</code>。保存后将立即写入并刷新运行中的模型实例，无需重启即可对新对话生效；
      所有变更均记入安全审计。
    </p>

    <div v-if="store.modelConfigLoading && !store.modelConfig.length" class="loading-box">加载中...</div>

    <div v-else class="form-card">
      <div
        v-for="field in store.modelConfig"
        :key="field.key"
        class="field-block"
        :class="{ 'field-secret': field.is_secret }"
      >
        <label class="field-label" :for="'cfg-' + field.key">
          {{ field.label }}
          <span v-if="field.required" class="req">*</span>
          <span v-if="field.is_secret" class="badge-secret">
            <i class="fas fa-lock"></i> 敏感
          </span>
          <span v-else class="badge-normal">明文</span>
        </label>

        <div class="field-input">
          <input
            :id="'cfg-' + field.key"
            v-model.trim="form[field.key]"
            :type="field.is_secret && !reveal[field.key] ? 'password' : 'text'"
            :placeholder="placeholderFor(field)"
            :disabled="loading"
            autocomplete="off"
            spellcheck="false"
            @input="clearError(field.key)"
          />
          <button
            v-if="field.is_secret"
            type="button"
            class="reveal-btn"
            :title="reveal[field.key] ? '隐藏' : '显示'"
            @click="reveal[field.key] = !reveal[field.key]"
          >
            <i :class="reveal[field.key] ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
          </button>
        </div>

        <p class="field-desc">{{ field.description }}</p>
        <p v-if="errors[field.key]" class="field-error">
          <i class="fas fa-circle-exclamation"></i> {{ errors[field.key] }}
        </p>
      </div>
    </div>

    <transition name="fade">
      <div v-if="feedback.message" class="feedback" :class="feedback.type">
        <i :class="feedback.type === 'success' ? 'fas fa-circle-check' : 'fas fa-circle-xmark'"></i>
        {{ feedback.message }}
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { useSuperAdminStore } from '@/stores/superAdmin';
import type { ModelConfigField, UpdateModelConfigRequest } from '@/types/user';

const store = useSuperAdminStore();

const loading = ref(false);
const form = reactive<Record<string, string>>({});
const reveal = reactive<Record<string, boolean>>({});
const errors = reactive<Record<string, string>>({});
const feedback = reactive<{ type: 'success' | 'error' | ''; message: string }>({
  type: '',
  message: '',
});

const KEY_MAP: Record<string, keyof UpdateModelConfigRequest> = {
  ARK_API_KEY: 'ark_api_key',
  BASE_URL: 'base_url',
  MODEL: 'model',
  GRADE_MODEL: 'grade_model',
  FAST_MODEL: 'fast_model',
};

const placeholderFor = (field: ModelConfigField) => {
  if (field.is_secret) {
    return field.is_set ? '已配置（留空则保持当前密钥不变）' : '请输入 API 密钥';
  }
  return `请输入 ${field.key}`;
};

const clearError = (key: string) => {
  if (errors[key]) errors[key] = '';
};

const formatTime = (iso: string) => {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
};

const hydrateForm = () => {
  for (const f of store.modelConfig) {
    // 敏感字段不回显明文：仅当未配置时给空，配置后保持空（隐藏现有值）
    form[f.key] = f.is_secret ? '' : f.value;
    reveal[f.key] = false;
    errors[f.key] = '';
  }
};

const validate = (): boolean => {
  for (const f of store.modelConfig) errors[f.key] = '';
  let ok = true;

  for (const f of store.modelConfig) {
    const val = (form[f.key] || '').trim();

    if (f.key === 'ARK_API_KEY') {
      // 已配置且留空 => 保持；未配置且留空 => 报错；填写则校验长度
      if (!f.is_set && !val) {
        errors[f.key] = 'API 密钥尚未配置，请填写';
        ok = false;
      } else if (val && val.length < 8) {
        errors[f.key] = 'API 密钥长度过短，请检查是否完整';
        ok = false;
      }
      continue;
    }

    if (f.key === 'BASE_URL') {
      if (!val) {
        errors[f.key] = 'API 地址不能为空';
        ok = false;
      } else if (!/^https?:\/\/.+/.test(val)) {
        errors[f.key] = '必须是合法的 http(s) 地址，例如 https://api.deepseek.com/v1';
        ok = false;
      }
      continue;
    }

    if (f.key === 'MODEL' || f.key === 'GRADE_MODEL') {
      if (!val) {
        errors[f.key] = '该模型名称不能为空';
        ok = false;
      } else if (val.length > 256) {
        errors[f.key] = '长度不能超过 256 个字符';
        ok = false;
      }
      continue;
    }

    // FAST_MODEL 选填，但填写后校验长度
    if (f.key === 'FAST_MODEL' && val.length > 256) {
      errors[f.key] = '长度不能超过 256 个字符';
      ok = false;
    }
  }

  return ok;
};

const buildPayload = (): UpdateModelConfigRequest => {
  const payload: UpdateModelConfigRequest = {};
  for (const f of store.modelConfig) {
    const mapKey = KEY_MAP[f.key];
    const val = (form[f.key] || '').trim();
    if (f.is_secret) {
      // 敏感字段：仅当填写了新值才提交，留空表示沿用
      if (val) payload[mapKey] = val;
    } else {
      payload[mapKey] = val;
    }
  }
  return payload;
};

const onSave = async () => {
  feedback.message = '';
  feedback.type = '';
  if (!validate()) {
    feedback.type = 'error';
    feedback.message = '请修正高亮的字段后再保存';
    return;
  }
  loading.value = true;
  try {
    const data = await store.updateModelConfig(buildPayload());
    hydrateForm();
    feedback.type = 'success';
    feedback.message = data.message || '模型配置已保存并生效';
  } catch (e: any) {
    feedback.type = 'error';
    feedback.message = e?.message || '保存失败';
  } finally {
    loading.value = false;
  }
};

const onReset = async () => {
  feedback.message = '';
  feedback.type = '';
  try {
    await store.fetchModelConfig();
    hydrateForm();
  } catch (e: any) {
    feedback.type = 'error';
    feedback.message = e?.message || '还原失败';
  }
};

onMounted(() => {
  if (!store.modelConfig.length) {
    store.fetchModelConfig().then(hydrateForm);
  } else {
    hydrateForm();
  }
});
</script>

<style scoped>
.model-config {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.section-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.section-title h3 {
  color: var(--primary-color);
  font-size: 1.2rem;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.applied-tag {
  font-size: 0.8rem;
  color: #1f7a46;
  background: #e7f6ec;
  padding: 4px 10px;
  border-radius: 12px;
  white-space: nowrap;
}
.btn-secondary,
.btn-primary {
  border: none;
  border-radius: 14px;
  padding: 8px 16px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}
.btn-secondary {
  background: var(--white);
  color: var(--primary-color);
  border: 1px solid var(--border-color, #e3eaf3);
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.08);
}
.btn-primary {
  background: var(--primary-color);
  color: #fff;
  box-shadow: var(--shadow);
}
.btn-secondary:disabled,
.btn-primary:disabled {
  opacity: 0.6;
  cursor: default;
}
.hint {
  font-size: 0.85rem;
  color: var(--text-light);
  background: var(--bg-color);
  border: 1px solid var(--border-color, #e3eaf3);
  border-radius: var(--border-radius);
  padding: 12px 14px;
  line-height: 1.6;
}
.hint code {
  background: #e8f1ff;
  color: var(--primary-color);
  padding: 1px 6px;
  border-radius: 6px;
  font-size: 0.82rem;
}
.form-card {
  background: var(--white);
  border: 1px solid var(--border-color, #e3eaf3);
  border-radius: var(--border-radius);
  box-shadow: var(--shadow);
  padding: 8px 18px;
}
.field-block {
  padding: 16px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}
.field-block:last-child {
  border-bottom: none;
}
.field-secret {
  background: linear-gradient(90deg, rgba(192, 57, 43, 0.04), transparent 60%);
  border-radius: 12px;
  padding-left: 12px;
  padding-right: 12px;
}
.field-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  color: var(--text-color);
  font-size: 0.95rem;
  margin-bottom: 8px;
}
.req {
  color: #c0392b;
}
.badge-secret,
.badge-normal {
  font-size: 0.68rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
}
.badge-secret {
  background: #ffe9e6;
  color: #c0392b;
}
.badge-normal {
  background: #eef2f7;
  color: #475569;
}
.field-input {
  display: flex;
  gap: 8px;
  align-items: stretch;
}
.field-input input {
  flex: 1;
  min-width: 0;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 12px;
  padding: 10px 12px;
  font-size: 0.92rem;
  color: var(--text-color);
  background: #fff;
  outline: none;
  transition: var(--transition);
}
.field-input input:focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}
.reveal-btn {
  flex: 0 0 auto;
  width: 44px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  background: #fff;
  border-radius: 12px;
  cursor: pointer;
  color: var(--text-light);
}
.reveal-btn:hover {
  color: var(--primary-color);
}
.field-desc {
  margin-top: 8px;
  font-size: 0.8rem;
  color: var(--text-light);
  line-height: 1.55;
}
.field-error {
  margin-top: 6px;
  font-size: 0.8rem;
  color: #c0392b;
}
.loading-box {
  text-align: center;
  color: var(--text-light);
  padding: 40px;
}
.feedback {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-radius: var(--border-radius);
  font-weight: 600;
  font-size: 0.92rem;
}
.feedback.success {
  background: #e7f6ec;
  color: #1f7a46;
}
.feedback.error {
  background: #fdeceb;
  color: #c0392b;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 640px) {
  .section-title h3 {
    font-size: 1.05rem;
  }
  .toolbar {
    width: 100%;
  }
  .toolbar .btn-secondary,
  .toolbar .btn-primary {
    flex: 1 1 auto;
  }
  .form-card {
    padding: 4px 12px;
  }
}
</style>
