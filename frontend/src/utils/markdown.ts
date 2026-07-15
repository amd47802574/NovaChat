import { marked } from 'marked';
import hljs from 'highlight.js';

// 自定义代码块渲染，并保留语法高亮
const renderer = new marked.Renderer();
renderer.code = (code, language) => {
  const validLanguage = language && hljs.getLanguage(language) ? language : 'plaintext';
  const highlighted = hljs.highlight(code, { language: validLanguage }).value;
  const languageLabel = validLanguage === 'plaintext' ? '文本' : validLanguage;
  return `<div class="code-block"><div class="code-toolbar"><span>${languageLabel}</span><button type="button" class="copy-code-btn" title="复制代码"><i class="far fa-copy"></i><span>复制</span></button></div><pre><code class="hljs language-${validLanguage}">${highlighted}</code></pre></div>`;
};

marked.use({
  renderer,
  breaks: true,
  gfm: true
});

export function parseMarkdown(text: string, msgIndex?: number | null): string {
  const html = marked.parse(text || '', { async: false }) as string;

  if (msgIndex === undefined || msgIndex === null) {
    return html;
  }

  let inCode = false;
  return html.split(/(<[^>]*>)/).map(part => {
    if (part.startsWith('<')) {
      if (part.startsWith('<code') || part.startsWith('<pre')) inCode = true;
      if (part.startsWith('</code') || part.startsWith('</pre')) inCode = false;
      return part;
    }
    if (!inCode) {
      return part.replace(/\[([\d\s,]+)\]/g, (match: string, p1: string) => {
        const numbers = p1.split(',').map((n: string) => n.trim()).filter((n: string) => /^\d+$/.test(n));
        if (numbers.length === 0) return match;
        return numbers.map(
          (n: string) => `<sup class="cite-ref" data-msg-index="${msgIndex}" data-chunk-index="${n}">[${n}]</sup>`
        ).join('');
      });
    }
    return part;
  }).join('');
}

export function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
