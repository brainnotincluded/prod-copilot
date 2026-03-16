<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'

const props = defineProps<{
  data: {
    id: number
    method: string
    path: string
    summary?: string | null
    description?: string | null
    parameters?: Array<Record<string, any>> | null
    color: string
  }
}>()

const METHOD_COLORS: Record<string, string> = {
  GET: '#34a853',
  POST: '#1a73e8',
  PUT: '#f59e0b',
  DELETE: '#ea4335',
  PATCH: '#673ab7',
  HEAD: '#607d8b',
  OPTIONS: '#795548',
}

const methodColor = computed(() => METHOD_COLORS[props.data.method] || '#9e9e9e')

const highlightedPath = computed(() => {
  return props.data.path.replace(
    /\{([^}]+)\}/g,
    '<span class="path-param">{$1}</span>'
  )
})

const truncatedSummary = computed(() => {
  const s = props.data.summary || ''
  return s.length > 50 ? s.slice(0, 47) + '...' : s
})
</script>

<template>
  <div class="endpoint-node" :style="{ '--method-color': methodColor }">
    <!-- Hierarchy: left/right -->
    <Handle type="target" :position="Position.Left" id="left" class="handle-dot" />
    <Handle type="source" :position="Position.Right" id="right" class="handle-dot" />
    <!-- FK refs: top -->
    <Handle type="target" :position="Position.Top" id="top-in" class="handle-dot" style="left: 30%" />
    <Handle type="source" :position="Position.Top" id="top-out" class="handle-dot" style="left: 70%" />
    <!-- Parent / nested: bottom -->
    <Handle type="target" :position="Position.Bottom" id="bottom-in" class="handle-dot" style="left: 30%" />
    <Handle type="source" :position="Position.Bottom" id="bottom-out" class="handle-dot" style="left: 70%" />
    <div class="ep-row">
      <span
        class="ep-method"
        :style="{
          background: methodColor,
          color: data.method === 'PUT' ? '#333' : '#fff',
        }"
      >
        {{ data.method }}
      </span>
      <span class="ep-path" v-html="highlightedPath"></span>
    </div>
    <div v-if="truncatedSummary" class="ep-summary">{{ truncatedSummary }}</div>
  </div>
</template>

<style scoped>
.endpoint-node {
  padding: 8px 12px;
  background: #fff;
  border: 1px solid #e4e4e7;
  border-left: 3px solid var(--method-color, #9e9e9e);
  border-radius: 6px;
  min-width: 190px;
  max-width: 260px;
  cursor: pointer;
  transition: box-shadow 0.2s ease, transform 0.15s ease;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.endpoint-node:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  transform: translateY(-1px);
}

.ep-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ep-method {
  font-size: 9px;
  font-weight: 700;
  padding: 2px 5px;
  border-radius: 3px;
  letter-spacing: 0.4px;
  flex-shrink: 0;
  line-height: 1.2;
}

.ep-path {
  font-size: 11.5px;
  font-weight: 500;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  color: #18181b;
  word-break: break-all;
  line-height: 1.3;
}

.ep-path :deep(.path-param) {
  color: #2563eb;
  font-weight: 600;
}

.ep-summary {
  font-size: 10px;
  color: #71717a;
  margin-top: 3px;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Handles - make them small and subtle */
.handle-dot {
  width: 5px !important;
  height: 5px !important;
  background: #d4d4d8 !important;
  border: 1px solid #fff !important;
  opacity: 0.6;
}

.endpoint-node:hover .handle-dot {
  opacity: 1;
  background: #a1a1aa !important;
}
</style>
