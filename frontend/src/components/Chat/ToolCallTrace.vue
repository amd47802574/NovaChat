<template>
  <div v-if="msg.toolCalls && msg.toolCalls.length" class="message-meta">
    <details class="reasoning-details tool-call-details" open>
      <summary>
        <i class="fas fa-wrench"></i>
        工具调用（{{ msg.toolCalls.length }}）
      </summary>
      <div class="reasoning-content">
        <ul class="tool-call-list">
          <li
            v-for="(call, idx) in msg.toolCalls"
            :key="call.call_id || `${call.tool_name}-${idx}`"
            class="tool-call-item"
          >
            <span class="tool-call-index">#{{ idx + 1 }}</span>
            <span class="tool-call-icon">🔧</span>
            <span class="tool-call-name">{{ call.tool_name }}</span>
            <span v-if="call.started_at" class="tool-call-time">
              {{ formatTime(call.started_at) }}
            </span>
          </li>
        </ul>
      </div>
    </details>
  </div>
</template>

<script setup lang="ts">
import type { Message } from '@/types/chat';

defineProps<{
  msg: Message;
}>();

const formatTime = (iso: string) => {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '';
    return d.toLocaleTimeString('zh-CN', { hour12: false });
  } catch {
    return '';
  }
};
</script>
