<template>
  <div class="message-content thinking-content">
    <div class="thinking-header">
      <div class="thinking-dots">
        <span class="tdot"></span>
        <span class="tdot"></span>
        <span class="tdot"></span>
      </div>
      <span v-if="!msg.ragSteps || !msg.ragSteps.length" class="thinking-text">正在思考中...</span>
      <span v-else class="thinking-text">{{ msg.ragSteps[msg.ragSteps.length - 1].label }}</span>
    </div>

    <!-- 工具调用过程（思考阶段实时展示） -->
    <div v-if="msg.toolCalls && msg.toolCalls.length" class="thinking-tool-calls">
      <div
        v-for="(call, idx) in msg.toolCalls"
        :key="call.call_id || `${call.tool_name}-${idx}`"
        class="thinking-tool-call-line"
      >
        <span class="thinking-trace-icon">🔧</span>
        <span class="thinking-trace-label">调用工具：{{ call.tool_name }}</span>
      </div>
    </div>
    
    <div v-if="msg.ragSteps && msg.ragSteps.length" class="thinking-trace-lines">
      <template v-for="(grp, gIdx) in msg._groupedSteps" :key="grp.group || `main-${gIdx}`">
        <!-- 子 Agent 分组：带标题可折叠 -->
        <div v-if="grp.group" class="step-group">
          <div class="step-group-header" @click="toggleGroup(gIdx)">
            <span class="step-group-arrow" :class="{ collapsed: grp.collapsed }">▶</span>
            <span class="step-group-label">🧵 子问题：{{ grp.label }}</span>
            <span class="step-group-count">{{ grp.steps.length }} 步</span>
          </div>
          <div v-show="!grp.collapsed" class="step-group-body">
            <div v-for="(step, sIdx) in grp.steps" :key="sIdx" class="thinking-trace-line">
              <span class="thinking-trace-icon">{{ step.icon || '▶' }}</span>
              <span class="thinking-trace-label">{{ step.label }}</span>
              <span v-if="step.detail" class="thinking-trace-detail">{{ step.detail }}</span>
            </div>
          </div>
        </div>
        
        <!-- 普通步骤：直接展示 -->
        <template v-else>
          <div v-for="(step, sIdx) in grp.steps" :key="'s' + gIdx + '-' + sIdx" class="thinking-trace-line">
            <span class="thinking-trace-icon">{{ step.icon || '▶' }}</span>
            <span class="thinking-trace-label">{{ step.label }}</span>
            <span v-if="step.detail" class="thinking-trace-detail">{{ step.detail }}</span>
          </div>
        </template>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useChatStore } from '@/stores/chat';
import type { Message } from '@/types/chat';

const props = defineProps<{
  msg: Message;
  msgIndex: number;
}>();

const chatStore = useChatStore();

const toggleGroup = (groupIndex: number) => {
  chatStore.toggleStepGroup(props.msgIndex, groupIndex);
};
</script>
