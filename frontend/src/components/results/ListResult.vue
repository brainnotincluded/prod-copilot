<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  data: Record<string, any>
  metadata?: Record<string, any>
}>()

const items = computed<any[]>(() => {
  if (Array.isArray(props.data.items)) return props.data.items
  if (Array.isArray(props.data)) return props.data
  return []
})

const title = computed(() => props.metadata?.title || '')

function getItemLabel(item: any): string {
  if (typeof item === 'string') return item
  if (typeof item === 'number') return String(item)
  return item.name || item.title || item.label || JSON.stringify(item)
}

function getItemDescription(item: any): string {
  if (typeof item !== 'object' || item === null) return ''
  return item.description || item.subtitle || item.detail || ''
}
</script>

<template>
  <div class="list-result result-fade-in">
    <div v-if="title" class="result-title">{{ title }}</div>
    <div v-if="items.length === 0" class="result-empty">Совпадений не найдено.</div>
    <ul v-else class="result-list">
      <li v-for="(item, index) in items" :key="index" class="list-item">
        <span class="item-index">{{ index + 1 }}</span>
        <div class="item-content">
          <span class="item-label">{{ getItemLabel(item) }}</span>
          <span v-if="getItemDescription(item)" class="item-desc">
            {{ getItemDescription(item) }}
          </span>
        </div>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.list-result {
  padding: 16px;
}

.result-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 12px;
}

.result-empty {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

.result-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.list-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border-light);
}

.list-item:last-child {
  border-bottom: none;
}

.item-index {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-bg-tertiary);
  color: var(--color-text-tertiary);
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.item-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.item-label {
  font-size: 14px;
  color: var(--color-text-primary);
  word-break: break-word;
}

.item-desc {
  font-size: 12px;
  color: var(--color-text-tertiary);
}
</style>
