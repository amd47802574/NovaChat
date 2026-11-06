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
    <span
      v-if="ttftMs !== undefined"
      class="ttft-stat"
      :title="'从发送消息到助手正文首个可见字符的耗时'"
    >
      {{ ttftMs < 1000 ? `首字 ${ttftMs} ms` : `首字 ${(ttftMs / 1000).toFixed(2)} 秒` }}
    </span>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  copied: boolean;
  ttftMs?: number;
}>();

defineEmits<{
  (e: 'copy'): void;
}>();
</script>
