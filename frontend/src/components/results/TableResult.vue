<script setup lang="ts">
import { computed, ref } from 'vue'
import { useLocale } from '@/composables/useLocale'

const { t } = useLocale()

const props = defineProps<{
  data: Record<string, any>
  metadata?: Record<string, any>
}>()

const title = computed(() => props.metadata?.title || '')
const rows = computed<any[]>(() => {
  if (Array.isArray(props.data.rows)) return props.data.rows
  if (Array.isArray(props.data)) return props.data
  return []
})

const columns = computed<string[]>(() => {
  if (Array.isArray(props.data.columns)) return props.data.columns
  if (rows.value.length > 0) {
    const firstRow = rows.value[0]
    if (Array.isArray(firstRow)) {
      // Array rows: generate numbered column headers
      return firstRow.map((_: any, i: number) => `col_${i}`)
    }
    return Object.keys(firstRow)
  }
  return []
})

const isArrayRows = computed(() => {
  return rows.value.length > 0 && Array.isArray(rows.value[0])
})

const sortColumn = ref<string | null>(null)
const sortDirection = ref<'asc' | 'desc'>('asc')
const filterText = ref('')

function toggleSort(col: string) {
  if (sortColumn.value === col) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortColumn.value = col
    sortDirection.value = 'asc'
  }
}

function getCellValue(row: any, col: string, colIndex: number): any {
  if (Array.isArray(row)) {
    return row[colIndex] ?? null
  }
  return row[col] ?? null
}

const filteredRows = computed(() => {
  let result = [...rows.value]

  if (filterText.value.trim()) {
    const query = filterText.value.toLowerCase()
    result = result.filter((row) =>
      columns.value.some((col, colIdx) =>
        String(getCellValue(row, col, colIdx) ?? '').toLowerCase().includes(query)
      )
    )
  }

  if (sortColumn.value) {
    const col = sortColumn.value
    const colIdx = columns.value.indexOf(col)
    const dir = sortDirection.value === 'asc' ? 1 : -1
    result.sort((a, b) => {
      const va = getCellValue(a, col, colIdx)
      const vb = getCellValue(b, col, colIdx)
      if (va == null && vb == null) return 0
      if (va == null) return dir
      if (vb == null) return -dir
      if (typeof va === 'number' && typeof vb === 'number') {
        return (va - vb) * dir
      }
      return String(va).localeCompare(String(vb)) * dir
    })
  }

  return result
})

function formatHeader(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function formatCell(value: any): string {
  if (value === null || value === undefined) return '--'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
</script>

<template>
  <div class="table-result">
    <div class="table-header">
      <span v-if="title" class="result-title">{{ title }}</span>
      <div class="table-controls">
        <div class="filter-input-container">
          <i class="pi pi-search filter-icon"></i>
          <input
            v-model="filterText"
            type="text"
            class="filter-input"
            :placeholder="t('results.filter')"
          />
        </div>
        <span class="row-count">{{ t('results.rows', filteredRows.length) }}</span>
      </div>
    </div>
    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th
              v-for="(col, colIdx) in columns"
              :key="col"
              class="table-th"
              @click="toggleSort(col)"
            >
              <span class="th-content">
                {{ isArrayRows ? t('results.column', colIdx + 1) : formatHeader(col) }}
                <i
                  v-if="sortColumn === col"
                  class="pi sort-icon"
                  :class="sortDirection === 'asc' ? 'pi-sort-amount-up' : 'pi-sort-amount-down'"
                ></i>
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="filteredRows.length === 0">
            <td :colspan="columns.length" class="table-empty">{{ t('results.noData') }}</td>
          </tr>
          <tr v-for="(row, idx) in filteredRows" :key="idx" class="table-row">
            <td v-for="(col, colIdx) in columns" :key="col" class="table-td">
              {{ formatCell(getCellValue(row, col, colIdx)) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.table-result {
  display: flex;
  flex-direction: column;
}

.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  gap: 12px;
  flex-wrap: wrap;
}

.result-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.table-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-input-container {
  position: relative;
}

.filter-icon {
  position: absolute;
  left: 8px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.filter-input {
  padding: 6px 10px 6px 28px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 12px;
  background: var(--color-bg);
  color: var(--color-text-primary);
  outline: none;
  width: 180px;
  transition: border-color var(--transition-fast);
}

.filter-input:focus {
  border-color: var(--color-accent);
}

.row-count {
  font-size: 12px;
  color: var(--color-text-tertiary);
  white-space: nowrap;
}

.table-wrapper {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.table-th {
  padding: 10px 16px;
  text-align: left;
  font-weight: 600;
  color: var(--color-text-secondary);
  background: var(--color-bg-secondary);
  border-bottom: 1px solid var(--color-border-light);
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}

.table-th:hover {
  color: var(--color-text-primary);
}

.th-content {
  display: flex;
  align-items: center;
  gap: 4px;
}

.sort-icon {
  font-size: 10px;
  color: var(--color-accent);
}

.table-row:hover {
  background: var(--color-bg-secondary);
}

.table-td {
  padding: 10px 16px;
  border-bottom: 1px solid var(--color-border-light);
  color: var(--color-text-primary);
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.table-empty {
  padding: 24px;
  text-align: center;
  color: var(--color-text-tertiary);
}
</style>
