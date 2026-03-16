<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
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
const filterExpanded = ref(false)
const viewMode = ref<'table' | 'cards'>('table')

// Responsive detection
const isMobile = ref(false)
const isTablet = ref(false)
const isManyColumns = computed(() => columns.value.length > 3)

function updateBreakpoint() {
  const width = window.innerWidth
  isMobile.value = width <= 640
  isTablet.value = width > 640 && width <= 768
}

onMounted(() => {
  updateBreakpoint()
  window.addEventListener('resize', updateBreakpoint)
  setupScrollShadows()
})

onUnmounted(() => {
  window.removeEventListener('resize', updateBreakpoint)
})

// Scroll shadows for horizontal scroll
const tableWrapperRef = ref<HTMLElement | null>(null)

function setupScrollShadows() {
  const wrapper = tableWrapperRef.value
  if (!wrapper) return

  const updateShadows = () => {
    const hasScrollLeft = wrapper.scrollLeft > 0
    const hasScrollRight = wrapper.scrollLeft < wrapper.scrollWidth - wrapper.clientWidth - 1
    wrapper.classList.toggle('scroll-left', hasScrollLeft)
    wrapper.classList.toggle('scroll-right', hasScrollRight)
  }

  wrapper.addEventListener('scroll', updateShadows, { passive: true })
  // Initial check
  setTimeout(updateShadows, 0)
  // Update on resize
  window.addEventListener('resize', updateShadows)
}

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

function toggleFilter() {
  filterExpanded.value = !filterExpanded.value
  if (!filterExpanded.value) {
    filterText.value = ''
  }
}

function toggleViewMode() {
  viewMode.value = viewMode.value === 'table' ? 'cards' : 'table'
}
</script>

<template>
  <div class="table-result">
    <div class="table-header">
      <span v-if="title" class="result-title">{{ title }}</span>
      <div class="table-controls">
        <div class="filter-input-container" :class="{ 'filter-expanded': filterExpanded }">
          <button class="filter-toggle-btn" @click="toggleFilter" :title="t('results.filter')">
            <i class="pi pi-search"></i>
          </button>
          <input
            v-model="filterText"
            type="text"
            class="filter-input"
            :placeholder="t('results.filter')"
            :class="{ 'filter-visible': filterExpanded }"
          />
        </div>
        <!-- View mode toggle for mobile with many columns -->
        <button
          v-if="isMobile && isManyColumns"
          class="view-mode-toggle"
          @click="toggleViewMode"
          :title="viewMode === 'table' ? t('results.cardsView') : t('results.tableView')"
        >
          <i class="pi" :class="viewMode === 'table' ? 'pi-th-large' : 'pi-table'"></i>
        </button>
        <span class="row-count">{{ t('results.rows', filteredRows.length) }}</span>
      </div>
    </div>
    
    <!-- Table View -->
    <div v-if="viewMode === 'table'" ref="tableWrapperRef" class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th
              v-for="(col, colIdx) in columns"
              :key="col"
              class="table-th"
              :class="{ 'mobile-hidden': isMobile && colIdx >= 3 && isManyColumns }"
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
            <td
              v-for="(col, colIdx) in columns"
              :key="col"
              class="table-td"
              :class="{ 'mobile-hidden': isMobile && colIdx >= 3 && isManyColumns }"
            >
              {{ formatCell(getCellValue(row, col, colIdx)) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Cards View (Mobile alternative) -->
    <div v-else class="cards-wrapper">
      <div v-if="filteredRows.length === 0" class="cards-empty">
        {{ t('results.noData') }}
      </div>
      <div
        v-for="(row, idx) in filteredRows"
        :key="idx"
        class="data-card"
      >
        <div
          v-for="(col, colIdx) in columns"
          :key="col"
          class="data-card-row"
        >
          <span class="data-card-label">
            {{ isArrayRows ? t('results.column', colIdx + 1) : formatHeader(col) }}
          </span>
          <span class="data-card-value">
            {{ formatCell(getCellValue(row, col, colIdx)) }}
          </span>
        </div>
      </div>
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
  display: flex;
  align-items: center;
}

.filter-toggle-btn {
  background: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 6px 10px;
  cursor: pointer;
  color: var(--color-text-tertiary);
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
}

.filter-toggle-btn:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.view-mode-toggle {
  background: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 6px 10px;
  cursor: pointer;
  color: var(--color-text-tertiary);
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  min-height: 36px;
}

.view-mode-toggle:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
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
  transition: border-color var(--transition-fast), width var(--transition-fast);
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
  position: relative;
}

/* Shadow indicators for horizontal scroll */
.table-wrapper::before,
.table-wrapper::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  width: 20px;
  pointer-events: none;
  opacity: 0;
  transition: opacity var(--transition-fast);
  z-index: 1;
}

.table-wrapper::before {
  left: 0;
  background: linear-gradient(to right, rgba(0, 0, 0, 0.1), transparent);
}

.table-wrapper::after {
  right: 0;
  background: linear-gradient(to left, rgba(0, 0, 0, 0.1), transparent);
}

.table-wrapper.scroll-left::before,
.table-wrapper.scroll-right::after {
  opacity: 1;
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
  min-height: 44px;
  height: 44px;
  box-sizing: border-box;
}

.table-th:hover {
  color: var(--color-text-primary);
}

.th-content {
  display: flex;
  align-items: center;
  gap: 4px;
  min-height: 44px;
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

/* Cards view styles */
.cards-wrapper {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cards-empty {
  padding: 24px;
  text-align: center;
  color: var(--color-text-tertiary);
  font-size: 12px;
}

.data-card {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: 12px;
  background: var(--color-bg);
}

.data-card-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-border-lightest);
}

.data-card-row:last-child {
  border-bottom: none;
}

.data-card-label {
  font-size: 11px;
  color: var(--color-text-tertiary);
  font-weight: 500;
  text-transform: capitalize;
  flex-shrink: 0;
  margin-right: 12px;
}

.data-card-value {
  font-size: 12px;
  color: var(--color-text-primary);
  text-align: right;
  word-break: break-word;
  max-width: 60%;
}

/* Tablet styles (641-768px) */
@media (max-width: 768px) {
  .table-header {
    padding: 10px 12px;
  }

  .result-title {
    font-size: 13px;
  }

  .table-th,
  .table-td {
    padding: 9px 14px;
  }

  .filter-input {
    width: 160px;
  }

  .data-table {
    font-size: 12px;
  }

  .table-td {
    max-width: 200px;
  }

  .cards-wrapper {
    padding: 10px;
    gap: 10px;
  }

  .data-card {
    padding: 10px;
  }

  .data-card-label {
    font-size: 10px;
  }

  .data-card-value {
    font-size: 11px;
  }
}

/* Mobile styles (< 640px) */
@media (max-width: 640px) {
  .table-header {
    padding: 8px 12px;
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }

  .table-controls {
    flex-wrap: wrap;
    gap: 8px;
  }

  .result-title {
    font-size: 13px;
  }

  /* Compact filter - only icon, expandable */
  .filter-input-container {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
  }

  .filter-toggle-btn {
    padding: 6px 8px;
    min-width: 44px;
    min-height: 44px;
  }

  .view-mode-toggle {
    min-width: 44px;
    min-height: 44px;
  }

  .filter-input {
    width: 0;
    padding: 0;
    border: none;
    opacity: 0;
    pointer-events: none;
    transition: all var(--transition-fast);
  }

  .filter-input.filter-visible {
    width: 140px;
    padding: 6px 10px 6px 28px;
    border: 1px solid var(--color-border);
    opacity: 1;
    pointer-events: auto;
  }

  .row-count {
    font-size: 11px;
    width: 100%;
    text-align: right;
    margin-top: 4px;
  }

  .data-table {
    font-size: 12px;
  }

  .table-th,
  .table-td {
    padding: 8px 12px;
  }

  /* Larger touch target for sorting on mobile */
  .table-th {
    min-height: 44px;
    height: auto;
    padding: 12px;
  }

  .th-content {
    min-height: 44px;
  }

  .table-td {
    max-width: 120px;
  }

  .table-empty {
    padding: 16px;
    font-size: 12px;
  }

  /* Enhanced horizontal scroll shadows */
  .table-wrapper::before,
  .table-wrapper::after {
    width: 30px;
  }

  .table-wrapper::before {
    background: linear-gradient(to right, rgba(0, 0, 0, 0.15), transparent);
  }

  .table-wrapper::after {
    background: linear-gradient(to left, rgba(0, 0, 0, 0.15), transparent);
  }

  /* Hide columns beyond first 3 on mobile with many columns */
  .mobile-hidden {
    display: none;
  }

  .cards-wrapper {
    padding: 8px;
    gap: 8px;
  }

  .data-card {
    padding: 10px;
    border-radius: var(--radius-sm);
  }

  .data-card-row {
    padding: 5px 0;
  }

  .data-card-label {
    font-size: 10px;
  }

  .data-card-value {
    font-size: 11px;
  }
}
</style>
