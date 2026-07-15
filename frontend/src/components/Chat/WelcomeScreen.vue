<template>
  <div class="welcome-screen">
    <div class="welcome-mark">
      <i class="fas fa-wand-magic-sparkles"></i>
    </div>
    <span class="welcome-kicker">NOVA KNOWLEDGE ENGINE</span>
    <h3>今天想探索什么？</h3>
    <p>连接你的知识库，获得带有可靠来源的清晰回答。</p>
    <div class="prompt-suggestions">
      <button v-for="item in suggestions" :key="item.text" type="button" @click="selectSuggestion(item.text)">
        <i :class="item.icon"></i>
        <span>{{ item.text }}</span>
        <i class="fas fa-arrow-up-right-from-square suggestion-arrow"></i>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useChatStore } from '@/stores/chat';

const chatStore = useChatStore();

const suggestions = [
  { icon: 'fas fa-file-lines', text: '总结知识库中的核心内容' },
  { icon: 'fas fa-code', text: '帮我分析一段代码的实现思路' },
  { icon: 'fas fa-magnifying-glass-chart', text: '对比文档中的关键观点' },
];

const selectSuggestion = (text: string) => {
  chatStore.userInput = text;
};
</script>
