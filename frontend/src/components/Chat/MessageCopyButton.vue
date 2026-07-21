<template>
  <div class="message-actions">
    <button
      type="button"
      class="copy-message-btn"
      :class="{ copied }"
      :title="copied ? '已复制' : '复制消息'"
      @click="$emit('copy')"
    >
      <i :class="copied ? 'fas fa-check' : 'far fa-copy'"></i>
      <span>{{ copied ? '已复制' : '复制' }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  copied: boolean;
}>();

defineEmits<{
  (e: 'copy'): void;
}>();
</script>
