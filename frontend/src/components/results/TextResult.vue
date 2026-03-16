<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

const props = defineProps<{
  data: Record<string, any>
  metadata?: Record<string, any>
}>()

const text = computed(() => {
  if (props.data.text) return props.data.text
  if (props.data.content) return props.data.content
  if (props.data.error) return props.data.error
  if (props.data.message) return props.data.message
  // Don't show empty JSON
  const json = JSON.stringify(props.data, null, 2)
  if (json === '{}' || json === '[]') return ''
  return json
})

const renderedText = computed(() => {
  const raw = text.value
  if (!raw || typeof raw !== 'string') return null
  // Check if content has markdown markers
  if (raw.includes('**') || raw.includes('`') || raw.includes('# ') || raw.startsWith('- ')) {
    return marked.parse(raw) as string
  }
  return null // null means use plain text
})

const title = computed(() => props.metadata?.title || '')
const hasText = computed(() => typeof text.value === 'string' && text.value.length > 0)
</script>

<template>
  <div v-if="hasText" class="text-result">
    <div v-if="title" class="result-title">{{ title }}</div>
    <div class="result-body">
      <div v-if="renderedText" class="result-text-md" v-html="renderedText"></div>
      <pre v-else class="result-text">{{ text }}</pre>
    </div>
  </div>
</template>

<style scoped>
.text-result {
  padding: 16px;
}

.result-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.result-body {
  overflow-x: auto;
}

.result-text {
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-primary);
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 0;
}

.result-text-md {
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-primary);
  word-wrap: break-word;
}

.result-text-md :deep(p) { margin: 0 0 8px 0; }
.result-text-md :deep(p:last-child) { margin-bottom: 0; }
.result-text-md :deep(code) {
  background: var(--color-bg-tertiary, #f5f5f5);
  padding: 1px 4px; border-radius: 3px;
  font-size: 0.9em; font-family: monospace;
}
.result-text-md :deep(pre) {
  background: var(--color-bg-tertiary, #f5f5f5);
  padding: 12px; border-radius: 6px; overflow-x: auto;
}
.result-text-md :deep(strong) { font-weight: 600; }
.result-text-md :deep(ul), .result-text-md :deep(ol) {
  padding-left: 20px; margin: 4px 0;
}
.result-text-md :deep(li) { margin: 2px 0; }
.result-text-md :deep(h1), .result-text-md :deep(h2), .result-text-md :deep(h3), .result-text-md :deep(h4) {
  margin: 8px 0 4px 0; font-weight: 600;
}
.result-text-md :deep(h1) { font-size: 1.3em; }
.result-text-md :deep(h2) { font-size: 1.15em; }
.result-text-md :deep(h3) { font-size: 1.05em; }
</style>
