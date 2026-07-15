<template>
  <div 
    class="message-content" 
    v-html="parsedHtml" 
    @click="onContentClick"
  ></div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { parseMarkdown, escapeHtml } from '@/utils/markdown';

const props = defineProps<{
  text: string;
  isUser: boolean;
  msgIndex?: number | null;
}>();

const emit = defineEmits<{
  (e: 'cite-click', msgIndex: number, chunkIndex: number): void;
}>();

const parsedHtml = computed(() => {
  if (props.isUser) {
    return escapeHtml(props.text);
  }
  return parseMarkdown(props.text, props.msgIndex);
});

const onContentClick = (e: MouseEvent) => {
  const copyButton = (e.target as HTMLElement).closest('.copy-code-btn');
  if (copyButton) {
    const code = copyButton.closest('.code-block')?.querySelector('code')?.textContent || '';
    navigator.clipboard.writeText(code).then(() => {
      copyButton.classList.add('copied');
      const label = copyButton.querySelector('span');
      if (label) label.textContent = '已复制';
      window.setTimeout(() => {
        copyButton.classList.remove('copied');
        if (label) label.textContent = '复制';
      }, 1400);
    });
    return;
  }

  const citeRef = (e.target as HTMLElement).closest('.cite-ref');
  if (!citeRef) return;
  const msgIndexStr = citeRef.getAttribute('data-msg-index');
  const chunkIndexStr = citeRef.getAttribute('data-chunk-index');
  if (msgIndexStr !== null && chunkIndexStr !== null) {
    emit('cite-click', Number(msgIndexStr), Number(chunkIndexStr));
  }
};
</script>
