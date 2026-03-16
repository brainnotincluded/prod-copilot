<script setup lang="ts">
import { computed } from 'vue'
import type { QueryResult } from '@/types'
import TextResult from './TextResult.vue'
import ListResult from './ListResult.vue'
import TableResult from './TableResult.vue'
import MapResult from './MapResult.vue'
import ChartResult from './ChartResult.vue'
import ImageResult from './ImageResult.vue'

const props = defineProps<{
  result: QueryResult
}>()

const resultComponent = computed(() => {
  switch (props.result.type) {
    case 'text':
      return TextResult
    case 'list':
      return ListResult
    case 'table':
      return TableResult
    case 'map':
      return MapResult
    case 'chart':
      return ChartResult
    case 'image':
      return ImageResult
    case 'dashboard':
      return null
    default:
      return TextResult
  }
})

const hasData = computed(() => {
  const d = props.result.data
  if (!d) return false
  if (typeof d === 'object' && Object.keys(d).length === 0) return false
  return true
})
const isDashboard = computed(() => props.result.type === 'dashboard')
const dashboardItems = computed(() => {
  if (!isDashboard.value) return []
  return (props.result.data.items || []) as QueryResult[]
})
</script>

<template>
  <div v-if="hasData" class="result-renderer result-fade-in">
    <template v-if="isDashboard">
      <div class="dashboard-grid">
        <div
          v-for="(item, index) in dashboardItems"
          :key="index"
          class="dashboard-item"
        >
          <ResultRenderer :result="item" />
        </div>
      </div>
    </template>
    <template v-else-if="resultComponent">
      <component :is="resultComponent" :data="result.data" :metadata="result.metadata" />
    </template>
  </div>
</template>

<style scoped>
.result-renderer {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--color-bg);
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
  padding: 16px;
}

.dashboard-item {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
}

/* Tablet styles (641-768px) */
@media (max-width: 768px) {
  .dashboard-grid {
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 14px;
    padding: 14px;
  }

  .dashboard-item {
    border-radius: var(--radius-sm);
  }
}

/* Mobile styles (< 640px) */
@media (max-width: 640px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
    gap: 12px;
    padding: 12px;
  }

  .dashboard-item {
    border-radius: 0;
    border-left: none;
    border-right: none;
  }

  .result-renderer {
    border-radius: 0;
    border-left: none;
    border-right: none;
  }
}
</style>
