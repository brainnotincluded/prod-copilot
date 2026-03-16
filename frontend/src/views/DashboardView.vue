<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useEndpointsStore } from '@/stores/endpoints'
import { useSwaggerStore } from '@/stores/swagger'
import { useLocale } from '@/composables/useLocale'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, PieChart, TooltipComponent, LegendComponent, GridComponent])

const endpointsStore = useEndpointsStore()
const swaggerStore = useSwaggerStore()
const { t } = useLocale()

onMounted(async () => {
  await Promise.all([
    endpointsStore.fetchEndpoints(),
    endpointsStore.fetchStats(),
    swaggerStore.fetchSwaggers(),
  ])
})

const stats = computed(() => endpointsStore.stats)
const sources = computed(() => swaggerStore.swaggers)
const isLoading = computed(() => endpointsStore.isLoading || swaggerStore.isLoading)

const methodColors: Record<string, string> = {
  GET: '#34a853',
  POST: '#1a73e8',
  PUT: '#fbbc04',
  PATCH: '#ff6d01',
  DELETE: '#ea4335',
  HEAD: '#80868b',
  OPTIONS: '#ab47bc',
}

const methodChartOption = computed(() => {
  const byMethod = stats.value?.by_method || {}
  const entries = Object.entries(byMethod).sort((a, b) => b[1] - a[1])
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { 
      bottom: 0, 
      textStyle: { fontSize: 11, color: '#5f6368' },
      itemWidth: 10,
      itemHeight: 10,
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '65%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 14, fontWeight: 600 },
          itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.15)' },
        },
        data: entries.map(([method, count]) => ({
          name: method,
          value: count,
          itemStyle: { color: methodColors[method] || '#80868b' },
        })),
      },
    ],
  }
})

const sourceChartOption = computed(() => {
  const bySource = stats.value?.by_source || {}
  const entries = Object.entries(bySource).sort((a, b) => b[1] - a[1]).slice(0, 10)
  const names = entries.map(([name]) => name.length > 20 ? name.slice(0, 18) + '...' : name)
  const values = entries.map(([, count]) => count)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 12, right: 20, top: 12, bottom: 4, containLabel: true },
    xAxis: {
      type: 'value',
      axisLabel: { fontSize: 10, color: '#5f6368' },
      splitLine: { lineStyle: { color: '#f1f3f4' } },
    },
    yAxis: {
      type: 'category',
      data: names.reverse(),
      axisLabel: { fontSize: 10, color: '#5f6368' },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: 'bar',
        data: values.reverse(),
        barMaxWidth: 24,
        itemStyle: { color: '#1a73e8', borderRadius: [0, 4, 4, 0] },
        emphasis: { itemStyle: { color: '#1557b0' } },
      },
    ],
  }
})

const sortedSources = computed(() => {
  return [...sources.value].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )
})

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}
</script>

<template>
  <div class="dashboard-view">
    <div class="dashboard-container">
      <!-- Loading skeleton -->
      <template v-if="isLoading && !stats">
        <div class="stats-row">
          <div v-for="i in 4" :key="i" class="stat-card">
            <div class="skeleton" style="width: 48px; height: 14px; margin-bottom: 8px"></div>
            <div class="skeleton" style="width: 64px; height: 28px"></div>
          </div>
        </div>
      </template>

      <!-- Stats cards -->
      <template v-else>
        <div class="stats-row">
          <div class="stat-card">
            <span class="stat-label">{{ t('dash.apiSources') }}</span>
            <span class="stat-value">{{ sources.length }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">{{ t('dash.endpoints') }}</span>
            <span class="stat-value">{{ stats?.total ?? 0 }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">{{ t('dash.httpMethods') }}</span>
            <span class="stat-value">{{ Object.keys(stats?.by_method || {}).length }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">{{ t('dash.avgPerSource') }}</span>
            <span class="stat-value">
              {{ sources.length ? Math.round((stats?.total ?? 0) / sources.length) : 0 }}
            </span>
          </div>
        </div>
      </template>

      <!-- Charts row -->
      <div class="charts-row" v-if="stats && stats.total > 0">
        <div class="chart-card">
          <h3 class="card-title">{{ t('dash.methods') }}</h3>
          <v-chart :option="methodChartOption" autoresize style="height: 260px" />
        </div>
        <div class="chart-card">
          <h3 class="card-title">{{ t('dash.bySource') }}</h3>
          <v-chart :option="sourceChartOption" autoresize style="height: 260px" />
        </div>
      </div>

      <!-- Sources table -->
      <div class="table-card" v-if="sortedSources.length > 0">
        <h3 class="card-title">{{ t('dash.sourcesTable') }}</h3>
        <div class="table-scroll-wrapper">
          <table class="sources-table">
            <thead>
              <tr>
                <th>{{ t('dash.name') }}</th>
                <th>{{ t('dash.baseUrl') }}</th>
                <th>{{ t('dash.endpointsCol') }}</th>
                <th>{{ t('dash.added') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="src in sortedSources" :key="src.id">
                <td class="source-name">{{ src.name }}</td>
                <td class="source-url">{{ src.base_url || '\u2014' }}</td>
                <td class="source-count">{{ src.endpoint_count }}</td>
                <td class="source-date">{{ formatDate(src.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Method breakdown -->
      <div class="method-cards" v-if="stats && stats.total > 0">
        <div
          v-for="(count, method) in stats.by_method"
          :key="method"
          class="method-badge"
          :style="{ '--badge-color': methodColors[method] || '#80868b' }"
        >
          <span class="method-name">{{ method }}</span>
          <span class="method-count">{{ count }}</span>
        </div>
      </div>

      <!-- Empty state -->
      <div class="dashboard-empty" v-if="!isLoading && (!stats || stats.total === 0)">
        <i class="pi pi-chart-bar empty-icon"></i>
        <h2 class="empty-title">{{ t('dash.noData') }}</h2>
        <p class="empty-description">{{ t('dash.noDataDesc') }}</p>
        <router-link to="/swagger" class="empty-action">{{ t('dash.uploadSpec') }}</router-link>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-view {
  flex: 1;
  overflow-y: auto;
  padding: 28px 32px;
}

.dashboard-container {
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* ---- Stats cards ---- */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card {
  background: var(--color-bg);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--transition-fast);
}

.stat-card:hover {
  box-shadow: var(--shadow-md);
}

.stat-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text-primary);
  line-height: 1.2;
}

/* ---- Charts ---- */
.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.chart-card {
  background: var(--color-bg);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: 20px 24px;
  box-shadow: var(--shadow-sm);
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 12px;
}

/* ---- Sources table ---- */
.table-card {
  background: var(--color-bg);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: 20px 24px;
  box-shadow: var(--shadow-sm);
}

.table-scroll-wrapper {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
  scrollbar-color: var(--color-border) transparent;
}

.table-scroll-wrapper::-webkit-scrollbar {
  height: 6px;
}

.table-scroll-wrapper::-webkit-scrollbar-track {
  background: transparent;
}

.table-scroll-wrapper::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 3px;
}

.sources-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  min-width: 500px;
}

.sources-table th {
  text-align: left;
  font-weight: 500;
  color: var(--color-text-secondary);
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border-light);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  white-space: nowrap;
}

.sources-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--color-border-light);
  color: var(--color-text-primary);
}

.sources-table tr:last-child td {
  border-bottom: none;
}

.sources-table tr:hover td {
  background: var(--color-bg-secondary);
}

.source-name {
  font-weight: 500;
  white-space: nowrap;
}

.source-url {
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: 12px;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-count {
  font-weight: 600;
  text-align: center;
  white-space: nowrap;
}

.source-date {
  color: var(--color-text-tertiary);
  font-size: 12px;
  white-space: nowrap;
}

/* ---- Method badges ---- */
.method-cards {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.method-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: var(--color-bg);
  border: 1px solid var(--color-border-light);
  border-left: 3px solid var(--badge-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.method-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--badge-color);
  font-family: var(--font-mono);
}

.method-count {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-text-primary);
}

/* ---- Empty state ---- */
.dashboard-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 80px 20px;
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  color: var(--color-border);
}

.empty-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.empty-description {
  font-size: 14px;
  color: var(--color-text-secondary);
  max-width: 420px;
  line-height: 1.6;
}

.empty-action {
  margin-top: 8px;
  padding: 12px 28px;
  background: var(--color-accent);
  color: white;
  border-radius: var(--radius-lg);
  font-size: 15px;
  font-weight: 500;
  text-decoration: none;
  transition: background var(--transition-fast);
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  touch-action: manipulation;
}

.empty-action:hover {
  background: var(--color-accent-hover);
  text-decoration: none;
}

.empty-action:active {
  transform: scale(0.98);
}

/* ---- Skeleton ---- */
.skeleton {
  background: linear-gradient(90deg, var(--color-bg-secondary) 25%, var(--color-border-light) 50%, var(--color-bg-secondary) 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: var(--radius-sm);
}

@keyframes skeleton-loading {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

/* ---- Responsive ---- */

/* Tablet (< 1024px) */
@media (max-width: 1024px) {
  .dashboard-view {
    padding: 24px 20px;
  }

  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .stat-card {
    padding: 18px 20px;
  }

  .stat-value {
    font-size: 26px;
  }
}

/* Tablet (< 768px) */
@media (max-width: 768px) {
  .dashboard-view {
    padding: 20px 16px;
  }

  .dashboard-container {
    gap: 20px;
  }

  .stats-row {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .stat-card {
    padding: 16px;
  }

  .stat-label {
    font-size: 11px;
  }

  .stat-value {
    font-size: 24px;
  }

  .charts-row {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .chart-card {
    padding: 16px;
  }

  .card-title {
    font-size: 13px;
    margin-bottom: 10px;
  }

  .table-card {
    padding: 16px;
  }

  .sources-table {
    font-size: 12px;
  }

  .sources-table th,
  .sources-table td {
    padding: 8px 10px;
  }

  .source-url {
    max-width: 150px;
  }

  .method-cards {
    gap: 8px;
  }

  .method-badge {
    padding: 6px 12px;
  }

  .method-name {
    font-size: 11px;
  }

  .method-count {
    font-size: 13px;
  }

  .dashboard-empty {
    padding: 60px 20px;
  }

  .empty-icon {
    font-size: 40px;
  }

  .empty-title {
    font-size: 18px;
  }

  .empty-action {
    padding: 12px 24px;
    font-size: 14px;
  }
}

/* Mobile (< 640px) */
@media (max-width: 640px) {
  .dashboard-view {
    padding: 16px 12px;
  }

  .dashboard-container {
    gap: 16px;
  }

  .stats-row {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }

  .stat-card {
    padding: 14px 12px;
    border-radius: var(--radius-md);
  }

  .stat-label {
    font-size: 10px;
    letter-spacing: 0.3px;
  }

  .stat-value {
    font-size: 22px;
  }

  .chart-card {
    padding: 14px 12px;
    border-radius: var(--radius-md);
  }

  .card-title {
    font-size: 13px;
    margin-bottom: 8px;
  }

  .table-card {
    padding: 14px 12px;
    border-radius: var(--radius-md);
  }

  .sources-table th {
    font-size: 10px;
    padding: 6px 8px;
  }

  .sources-table td {
    padding: 8px;
  }

  .source-name {
    font-size: 12px;
  }

  .source-url {
    font-size: 11px;
    max-width: 100px;
  }

  .source-date {
    font-size: 11px;
  }

  .method-cards {
    gap: 6px;
  }

  .method-badge {
    padding: 6px 10px;
    border-radius: var(--radius-sm);
  }

  .method-name {
    font-size: 11px;
  }

  .method-count {
    font-size: 12px;
  }

  .dashboard-empty {
    padding: 48px 16px;
    gap: 12px;
  }

  .empty-icon {
    font-size: 36px;
  }

  .empty-title {
    font-size: 17px;
  }

  .empty-description {
    font-size: 13px;
  }

  .empty-action {
    padding: 14px 24px;
    font-size: 14px;
    min-height: 48px;
    width: 100%;
    max-width: 280px;
  }
}

/* Small mobile (< 480px) - 1 колонка для статов */
@media (max-width: 480px) {
  .stats-row {
    grid-template-columns: 1fr;
  }

  .stat-card {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px;
  }

  .stat-label {
    font-size: 11px;
  }

  .stat-value {
    font-size: 24px;
  }
}

/* Small mobile (< 375px) */
@media (max-width: 375px) {
  .dashboard-view {
    padding: 12px 10px;
  }

  .stat-card {
    padding: 12px 14px;
  }

  .stat-value {
    font-size: 22px;
  }

  .chart-card,
  .table-card {
    padding: 12px;
  }

  .sources-table th,
  .sources-table td {
    padding: 6px;
  }

  .method-badge {
    padding: 5px 8px;
  }
}
</style>
