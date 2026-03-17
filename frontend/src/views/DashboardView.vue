<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useLocale } from '@/composables/useLocale'
import { useAuth } from '@/composables/useAuth'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart, LineChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, GridComponent, DataZoomComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, PieChart, LineChart, TooltipComponent, LegendComponent, GridComponent, DataZoomComponent])

const { t } = useLocale()
const { getAuthHeaders } = useAuth()

interface KPI {
  total_users: number
  active_users: number
  avg_check: number
  conversion_rate: number
  retention_rate: number
  period: string
}

interface Segment {
  id: number
  name: string
  description: string
  estimated_size: number
  status: string
  criteria: Record<string, any>
}

interface Audience {
  id: number
  name: string
  size: number
  status: string
  segment_name: string
  filters: Record<string, any>
}

interface Campaign {
  id: number
  title: string
  channel: string
  status: string
  audience_name: string
  audience_size: number
  message_variants: { variant: string; title: string; body: string; weight: number }[]
  kpis?: { total_impressions: number; total_clicks: number; total_conversions: number; ctr: number; conversion_rate: number }
}

interface DailyMetric {
  date: string
  impressions: number
  clicks: number
  conversions: number
  ctr: number
  conversion_rate: number
}

interface UserStats {
  by_segment: { segment: string; count: number; avg_check: number }[]
  by_status: { status: string; count: number }[]
}

const isLoading = ref(true)
const error = ref<string | null>(null)
const kpi = ref<KPI | null>(null)
const segments = ref<Segment[]>([])
const audiences = ref<Audience[]>([])
const campaigns = ref<Campaign[]>([])
const userStats = ref<UserStats | null>(null)
const campaignPerformance = ref<DailyMetric[]>([])
const selectedSegment = ref<Segment | null>(null)
const selectedCampaign = ref<Campaign | null>(null)

async function fetchDashboard() {
  isLoading.value = true
  error.value = null
  try {
    const headers = getAuthHeaders()
    const resp = await fetch('/api/v1/dashboard/live', { headers })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()

    kpi.value = data.kpi && data.kpi.total_users ? data.kpi : null
    segments.value = data.segments || []
    audiences.value = data.audiences || []
    campaigns.value = data.campaigns || []
    userStats.value = data.user_stats || null
    campaignPerformance.value = data.campaign_performance || []
  } catch (e: any) {
    error.value = e.message || 'Failed to load dashboard'
  } finally {
    isLoading.value = false
  }
}

onMounted(fetchDashboard)

const hasData = computed(() => kpi.value || segments.value.length > 0)

// ── KPI cards ──
const kpiCards = computed(() => {
  if (!kpi.value) return []
  return [
    { label: 'Total Users', value: kpi.value.total_users.toLocaleString(), icon: 'pi-users', color: '#1a73e8' },
    { label: 'Active Users', value: kpi.value.active_users.toLocaleString(), icon: 'pi-user-plus', color: '#34a853', sub: `${((kpi.value.active_users / kpi.value.total_users) * 100).toFixed(1)}%` },
    { label: 'Avg Check', value: `${Math.round(kpi.value.avg_check).toLocaleString()} ₽`, icon: 'pi-wallet', color: '#fbbc04' },
    { label: 'Conversion', value: `${kpi.value.conversion_rate}%`, icon: 'pi-chart-line', color: '#ea4335' },
    { label: 'Retention', value: `${kpi.value.retention_rate}%`, icon: 'pi-replay', color: '#ab47bc' },
  ]
})

// ── Audience by segment (pie) ──
const segmentPieOption = computed(() => {
  if (!userStats.value?.by_segment) return null
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 11, color: 'var(--color-text-secondary)' }, itemWidth: 10, itemHeight: 10 },
    series: [{
      type: 'pie',
      radius: ['38%', '62%'],
      center: ['50%', '42%'],
      itemStyle: { borderRadius: 6, borderColor: 'var(--color-bg)', borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 13, fontWeight: 600 } },
      data: userStats.value.by_segment.map((s, i) => ({
        name: s.segment,
        value: s.count,
        itemStyle: { color: ['#1a73e8', '#34a853', '#fbbc04', '#ea4335', '#ab47bc', '#ff6d01'][i % 6] },
      })),
    }],
  }
})

// ── Campaign performance (line) ──
const perfChartOption = computed(() => {
  if (!campaignPerformance.value.length) return null
  const dates = campaignPerformance.value.map(m => m.date.slice(5))
  return {
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, textStyle: { fontSize: 11, color: 'var(--color-text-secondary)' } },
    grid: { left: 12, right: 12, top: 24, bottom: 40, containLabel: true },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10, color: 'var(--color-text-tertiary)' } },
    yAxis: [
      { type: 'value', name: 'Count', axisLabel: { fontSize: 10, color: 'var(--color-text-tertiary)' }, splitLine: { lineStyle: { color: 'var(--color-border-light)' } } },
      { type: 'value', name: 'Rate %', axisLabel: { fontSize: 10, color: 'var(--color-text-tertiary)' }, splitLine: { show: false } },
    ],
    series: [
      { name: 'Impressions', type: 'bar', data: campaignPerformance.value.map(m => m.impressions), itemStyle: { color: '#1a73e8', borderRadius: [3, 3, 0, 0] }, barMaxWidth: 20 },
      { name: 'Clicks', type: 'bar', data: campaignPerformance.value.map(m => m.clicks), itemStyle: { color: '#34a853', borderRadius: [3, 3, 0, 0] }, barMaxWidth: 20 },
      { name: 'CTR %', type: 'line', yAxisIndex: 1, data: campaignPerformance.value.map(m => m.ctr), lineStyle: { color: '#ea4335', width: 2 }, itemStyle: { color: '#ea4335' }, smooth: true },
    ],
  }
})

// ── Avg check by segment (bar) ──
const avgCheckOption = computed(() => {
  if (!userStats.value?.by_segment) return null
  const sorted = [...userStats.value.by_segment].sort((a, b) => b.avg_check - a.avg_check)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 12, right: 20, top: 8, bottom: 4, containLabel: true },
    xAxis: { type: 'value', axisLabel: { fontSize: 10, color: 'var(--color-text-tertiary)' }, splitLine: { lineStyle: { color: 'var(--color-border-light)' } } },
    yAxis: { type: 'category', data: sorted.map(s => s.segment.length > 22 ? s.segment.slice(0, 20) + '…' : s.segment).reverse(), axisLabel: { fontSize: 10, color: 'var(--color-text-tertiary)' }, axisLine: { show: false }, axisTick: { show: false } },
    series: [{ type: 'bar', data: sorted.map(s => Math.round(s.avg_check)).reverse(), barMaxWidth: 20, itemStyle: { color: '#fbbc04', borderRadius: [0, 4, 4, 0] } }],
  }
})

const statusColor: Record<string, string> = {
  completed: 'var(--color-success)',
  active: '#1a73e8',
  draft: 'var(--color-text-tertiary)',
  scheduled: '#fbbc04',
  ready: 'var(--color-success)',
  building: '#1a73e8',
}

function formatDate(d: string) {
  return new Date(d).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}
</script>

<template>
  <div class="dashboard-view">
    <div class="dashboard-container">
      <!-- Header -->
      <div class="dash-header">
        <div>
          <h1 class="dash-title">{{ t('nav.dashboard') }}</h1>
          <p class="dash-subtitle">Auto-generated from connected APIs</p>
        </div>
        <button class="refresh-btn" @click="fetchDashboard" :disabled="isLoading">
          <i class="pi pi-refresh" :class="{ 'pi-spin': isLoading }"></i>
        </button>
      </div>

      <!-- Loading -->
      <div v-if="isLoading" class="dash-loading">
        <div class="kpi-row">
          <div v-for="i in 5" :key="i" class="kpi-card skeleton-card">
            <div class="skeleton" style="width:60px;height:12px;margin-bottom:8px"></div>
            <div class="skeleton" style="width:80px;height:28px"></div>
          </div>
        </div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="dash-error">
        <i class="pi pi-exclamation-triangle"></i>
        <p>{{ error }}</p>
        <button @click="fetchDashboard" class="retry-btn">Retry</button>
      </div>

      <!-- Empty -->
      <div v-else-if="!hasData" class="dash-empty">
        <i class="pi pi-chart-bar empty-icon"></i>
        <h2>No data yet</h2>
        <p>Upload a Swagger spec and run queries to populate the dashboard.</p>
        <router-link to="/swagger" class="empty-action">Upload API Spec</router-link>
      </div>

      <!-- Data -->
      <template v-else>
        <!-- KPI Cards -->
        <div class="kpi-row" v-if="kpiCards.length">
          <div v-for="card in kpiCards" :key="card.label" class="kpi-card">
            <div class="kpi-icon" :style="{ background: card.color + '18', color: card.color }">
              <i class="pi" :class="card.icon"></i>
            </div>
            <div class="kpi-info">
              <span class="kpi-label">{{ card.label }}</span>
              <span class="kpi-value">{{ card.value }}</span>
              <span v-if="card.sub" class="kpi-sub">{{ card.sub }}</span>
            </div>
          </div>
        </div>

        <!-- Charts row -->
        <div class="charts-row">
          <div class="chart-card" v-if="segmentPieOption">
            <h3 class="card-title"><i class="pi pi-users"></i> Audience by Segment</h3>
            <v-chart :option="segmentPieOption" autoresize style="height:280px" />
          </div>
          <div class="chart-card" v-if="avgCheckOption">
            <h3 class="card-title"><i class="pi pi-wallet"></i> Avg Check by Segment</h3>
            <v-chart :option="avgCheckOption" autoresize style="height:280px" />
          </div>
        </div>

        <!-- Campaign Performance -->
        <div class="chart-card full-width" v-if="perfChartOption">
          <h3 class="card-title"><i class="pi pi-chart-line"></i> Campaign Performance — {{ campaigns[0]?.title }}</h3>
          <v-chart :option="perfChartOption" autoresize style="height:300px" />
        </div>

        <!-- Segments Cards -->
        <div class="section" v-if="segments.length">
          <h3 class="section-title"><i class="pi pi-filter"></i> Segments</h3>
          <div class="entity-cards">
            <div
              v-for="seg in segments"
              :key="seg.id"
              class="entity-card clickable"
              :class="{ active: selectedSegment?.id === seg.id }"
              @click="selectedSegment = selectedSegment?.id === seg.id ? null : seg"
            >
              <div class="entity-header">
                <span class="entity-name">{{ seg.name }}</span>
                <span class="entity-badge" :style="{ background: statusColor[seg.status] || '#80868b' }">{{ seg.status }}</span>
              </div>
              <div class="entity-metric">
                <span class="metric-value">{{ seg.estimated_size?.toLocaleString() }}</span>
                <span class="metric-label">estimated size</span>
              </div>
              <p class="entity-desc">{{ seg.description }}</p>
              <!-- Detail expand -->
              <div v-if="selectedSegment?.id === seg.id" class="entity-detail">
                <div class="detail-title">Criteria</div>
                <div class="detail-json">
                  <div v-for="(val, key) in seg.criteria" :key="String(key)" class="detail-row">
                    <span class="detail-key">{{ key }}</span>
                    <span class="detail-val">{{ val }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Audiences Table -->
        <div class="section" v-if="audiences.length">
          <h3 class="section-title"><i class="pi pi-users"></i> Audiences</h3>
          <div class="table-card">
            <div class="table-scroll">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Segment</th>
                    <th>Size</th>
                    <th>Status</th>
                    <th>Filters</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="a in audiences" :key="a.id">
                    <td class="td-name">{{ a.name }}</td>
                    <td>{{ a.segment_name }}</td>
                    <td class="td-num">{{ a.size.toLocaleString() }}</td>
                    <td><span class="status-dot" :style="{ background: statusColor[a.status] || '#80868b' }"></span> {{ a.status }}</td>
                    <td class="td-mono">{{ Object.entries(a.filters || {}).map(([k,v]) => `${k}=${v}`).join(', ') || '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- Campaigns -->
        <div class="section" v-if="campaigns.length">
          <h3 class="section-title"><i class="pi pi-megaphone"></i> Campaigns</h3>
          <div class="entity-cards">
            <div
              v-for="camp in campaigns"
              :key="camp.id"
              class="entity-card campaign-card clickable"
              :class="{ active: selectedCampaign?.id === camp.id }"
              @click="selectedCampaign = selectedCampaign?.id === camp.id ? null : camp"
            >
              <div class="entity-header">
                <span class="entity-name">{{ camp.title }}</span>
                <span class="entity-badge" :style="{ background: statusColor[camp.status] || '#80868b' }">{{ camp.status }}</span>
              </div>
              <div class="campaign-meta">
                <span><i class="pi pi-send"></i> {{ camp.channel }}</span>
                <span><i class="pi pi-users"></i> {{ camp.audience_name }} ({{ camp.audience_size }})</span>
              </div>
              <!-- KPIs -->
              <div v-if="camp.kpis" class="campaign-kpis">
                <div class="mini-kpi">
                  <span class="mini-val">{{ camp.kpis.total_impressions?.toLocaleString() }}</span>
                  <span class="mini-label">impressions</span>
                </div>
                <div class="mini-kpi">
                  <span class="mini-val">{{ camp.kpis.total_clicks?.toLocaleString() }}</span>
                  <span class="mini-label">clicks</span>
                </div>
                <div class="mini-kpi">
                  <span class="mini-val">{{ camp.kpis.ctr }}%</span>
                  <span class="mini-label">CTR</span>
                </div>
                <div class="mini-kpi">
                  <span class="mini-val">{{ camp.kpis.conversion_rate }}%</span>
                  <span class="mini-label">conv.</span>
                </div>
              </div>
              <!-- Variants detail -->
              <div v-if="selectedCampaign?.id === camp.id && camp.message_variants" class="entity-detail">
                <div class="detail-title">Message Variants</div>
                <div v-for="v in camp.message_variants" :key="v.variant" class="variant-card">
                  <div class="variant-header">
                    <span class="variant-badge">{{ v.variant }}</span>
                    <span class="variant-weight">{{ v.weight }}%</span>
                  </div>
                  <div class="variant-title">{{ v.title }}</div>
                  <div class="variant-body">{{ v.body }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.dashboard-view {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
  background: var(--color-bg-secondary);
}

.dashboard-container {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── Header ── */
.dash-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.dash-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin: 0;
}

.dash-subtitle {
  font-size: 13px;
  color: var(--color-text-tertiary);
  margin: 4px 0 0;
}

.refresh-btn {
  width: 36px;
  height: 36px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  color: var(--color-text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
}

.refresh-btn:hover { background: var(--color-bg-tertiary); }
.refresh-btn:disabled { opacity: 0.5; cursor: default; }

/* ── KPI Row ── */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}

.kpi-card {
  background: var(--color-bg);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: 16px;
  display: flex;
  gap: 12px;
  align-items: center;
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--transition-fast);
}

.kpi-card:hover { box-shadow: var(--shadow-md); }

.kpi-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.kpi-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.kpi-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text-primary);
  line-height: 1.2;
}

.kpi-sub {
  font-size: 11px;
  color: var(--color-success);
  font-weight: 500;
}

/* ── Charts ── */
.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.chart-card {
  background: var(--color-bg);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: 20px;
  box-shadow: var(--shadow-sm);
}

.chart-card.full-width {
  grid-column: 1 / -1;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title i {
  font-size: 14px;
  color: var(--color-accent);
}

/* ── Section ── */
.section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-title i {
  font-size: 16px;
  color: var(--color-accent);
}

/* ── Entity Cards ── */
.entity-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.entity-card {
  background: var(--color-bg);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: 16px;
  box-shadow: var(--shadow-sm);
  transition: all var(--transition-fast);
}

.entity-card.clickable { cursor: pointer; }
.entity-card.clickable:hover { box-shadow: var(--shadow-md); border-color: var(--color-accent); }
.entity-card.active { border-color: var(--color-accent); box-shadow: 0 0 0 1px var(--color-accent); }

.entity-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.entity-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.entity-badge {
  font-size: 10px;
  font-weight: 600;
  color: white;
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.entity-metric {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: 6px;
}

.metric-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-accent);
}

.metric-label {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.entity-desc {
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.5;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ── Detail expand ── */
.entity-detail {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-light);
}

.detail-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.3px;
  margin-bottom: 8px;
}

.detail-json {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-row {
  display: flex;
  gap: 8px;
  font-size: 12px;
}

.detail-key {
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  min-width: 120px;
}

.detail-val {
  color: var(--color-text-primary);
  font-weight: 500;
}

/* ── Campaign specifics ── */
.campaign-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 10px;
}

.campaign-meta i {
  font-size: 11px;
  margin-right: 4px;
}

.campaign-kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.mini-kpi {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 6px;
  background: var(--color-bg-secondary);
  border-radius: var(--radius-sm);
}

.mini-val {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-text-primary);
}

.mini-label {
  font-size: 9px;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
}

/* ── Variants ── */
.variant-card {
  background: var(--color-bg-secondary);
  border-radius: var(--radius-md);
  padding: 10px;
  margin-bottom: 8px;
}

.variant-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.variant-badge {
  font-size: 10px;
  font-weight: 700;
  background: var(--color-accent);
  color: white;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
}

.variant-weight {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.variant-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 2px;
}

.variant-body {
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.4;
}

/* ── Table ── */
.table-card {
  background: var(--color-bg);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.data-table th {
  text-align: left;
  font-weight: 500;
  color: var(--color-text-secondary);
  padding: 10px 14px;
  border-bottom: 1px solid var(--color-border-light);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  background: var(--color-bg-secondary);
  white-space: nowrap;
}

.data-table td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--color-border-light);
  color: var(--color-text-primary);
}

.data-table tr:last-child td { border-bottom: none; }
.data-table tr:hover td { background: var(--color-bg-secondary); }

.td-name { font-weight: 500; white-space: nowrap; }
.td-num { font-weight: 600; font-variant-numeric: tabular-nums; }
.td-mono { font-family: var(--font-mono); font-size: 11px; color: var(--color-text-tertiary); }

.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 4px;
  vertical-align: middle;
}

/* ── States ── */
.dash-loading, .dash-error, .dash-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  gap: 12px;
}

.dash-error i { font-size: 40px; color: var(--color-error); }
.dash-error p { color: var(--color-text-secondary); margin: 0; }

.retry-btn {
  padding: 8px 20px;
  background: var(--color-accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
}

.dash-empty .empty-icon { font-size: 48px; color: var(--color-border); }
.dash-empty h2 { font-size: 20px; color: var(--color-text-primary); margin: 0; }
.dash-empty p { font-size: 14px; color: var(--color-text-secondary); margin: 0; }

.empty-action {
  padding: 10px 24px;
  background: var(--color-accent);
  color: white;
  border-radius: var(--radius-lg);
  text-decoration: none;
  font-weight: 500;
}

.empty-action:hover { background: var(--color-accent-hover); text-decoration: none; }

/* ── Skeleton ── */
.skeleton-card { justify-content: center; }
.skeleton {
  background: linear-gradient(90deg, var(--color-bg-secondary) 25%, var(--color-border-light) 50%, var(--color-bg-secondary) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}

@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

/* ── Responsive ── */
@media (max-width: 1024px) {
  .kpi-row { grid-template-columns: repeat(3, 1fr); }
}

@media (max-width: 768px) {
  .dashboard-view { padding: 16px; }
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
  .charts-row { grid-template-columns: 1fr; }
  .entity-cards { grid-template-columns: 1fr; }
  .campaign-kpis { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 480px) {
  .kpi-row { grid-template-columns: 1fr; }
  .kpi-card { padding: 12px; }
  .kpi-value { font-size: 18px; }
}
</style>
