<template>
  <div class="field-block field-secret">
    <label class="field-label">
      {{ label }}
      <span class="badge-secret"><i class="fas fa-lock"></i> 敏感</span>
    </label>

    <div class="field-input">
      <input
        v-model="value"
        :type="visible ? 'text' : 'password'"
        :placeholder="isSet ? '已配置（留空则保持当前密钥不变）' : placeholder"
        :disabled="disabled"
        autocomplete="new-password"
        spellcheck="false"
      />
      <button
        type="button"
        class="reveal-btn"
        :title="visible ? '隐藏' : '显示'"
        :aria-label="visible ? '隐藏 API Key' : '显示 API Key'"
        @click="visible = !visible"
      >
        <i :class="visible ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
      </button>
    </div>

    <p class="field-desc">{{ description }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

const props = withDefaults(defineProps<{
  modelValue: string;
  label: string;
  isSet: boolean;
  description: string;
  placeholder?: string;
  disabled?: boolean;
}>(), {
  placeholder: '请输入 API Key',
  disabled: false,
});

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void;
}>();

const visible = ref(false);
const value = computed({
  get: () => props.modelValue,
  set: (nextValue: string) => emit('update:modelValue', nextValue.trim()),
});
</script>

<style scoped>
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
  margin: 0 0 8px;
  color: var(--text-color);
  font-size: 0.95rem;
  font-weight: 700;
}
.badge-secret {
  padding: 2px 8px;
  border-radius: 10px;
  background: #ffe9e6;
  color: #c0392b;
  font-size: 0.68rem;
  font-weight: 600;
}
.field-input {
  display: flex;
  align-items: stretch;
  gap: 8px;
}
.field-input input {
  flex: 1;
  min-width: 0;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 12px;
  padding: 10px 12px;
  color: var(--text-color);
  background: #fff;
  font-size: 0.92rem;
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
  border-radius: 12px;
  color: var(--text-light);
  background: #fff;
  cursor: pointer;
}
.reveal-btn:hover {
  color: var(--primary-color);
}
.field-desc {
  margin-top: 8px;
  color: var(--text-light);
  font-size: 0.8rem;
  line-height: 1.55;
}
</style>
