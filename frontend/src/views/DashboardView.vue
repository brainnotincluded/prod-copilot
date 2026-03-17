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

// ── Types ──

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

interface Conversation {
  id: number
  title: string
  created_at: string
  updated_at: string
  message_count: number
  preview: string | null
}

interface Scenario {
  id: number
  correlation_id: string
  query: string
  status: string
  summary: { total_steps?: number; completed?: number; result_type?: string; error?: string } | null
  created_at: string
  finished_at: string | null
}

// ── State ──

const isLoading = ref(true)
const error = ref<string | null>(null)
const kpi = ref<KPI | null>(null)
const segments = ref<Segment[]>([])
const audiences = ref<Audience[]>([])
const campaigns = ref<Campaign[]>([])
const userStats = ref<UserStats | null>(null)
const campaignPerformance = ref<DailyMetric[]>([])
const conversations = ref<Conversation[]>([])
const scenarios = ref<Scenario[]>([])
const selectedSegment = ref<Segment | null>(null)
const selectedCampaign = ref<Campaign | null>(null)
const activeLogTab = ref<'all' | 'scenarios' | 'conversations'>('all')

// ── Data fetching ──

async function fetchDashboard() {
  isLoading.value = true
  error.value = null
  try {
    const headers = getAuthHeaders()

    // Parallel fetch: dashboard live data + conversations + scenarios
    const [dashResp, convResp, scenResp] = await Promise.allSettled([
      fetch('/api/v1/dashboard/live', { headers }),
      fetch('/api/v1/history/conversations?limit=10', { headers }),
      fetch('/api/v1/scenarios?limit=10', { headers }),
    ])

    // Process dashboard data
    if (dashResp.status === 'fulfilled' && dashResp.value.ok) {
      const data = await dashResp.value.json()
      kpi.value = data.kpi && data.kpi.total_users ? data.kpi : null
      segments.value = data.segments || []
      audiences.value = data.audiences || []
      campaigns.value = data.campaigns || []
      userStats.value = data.user_stats || null
      campaignPerformance.value = data.campaign_performance || []
    }

    // Process conversations
    if (convResp.status === 'fulfilled' && convResp.value.ok) {
      conversations.value = await convResp.value.json()
    }

    // Process scenarios
    if (scenResp.status === 'fulfilled' && scenResp.value.ok) {
      scenarios.value = await scenResp.value.json()
    }

  } catch (e: any) {
    error.value = e.message || 'Failed to load dashboard'
  } finally {
    isLoading.value = false
  }
}

onMounted(fetchDashboard)

const hasData = computed(() => kpi.value || segments.value.length > 0 || conversations.value.length > 0 || scenarios.value.length > 0)

// ── KPI cards ──

const kpiCards = computed(() => {
  if (!kpi.value) return []
  const k = kpi.value
  const activePercent = k.total_users > 0 ? ((k.active_users / k.total_users) * 100).toFixed(1) : '0'
  return [
    { label: 'Total Users', value: k.total_users.toLocaleString(), icon: 'pi-users', color: '#1a73e8', delta: null },
    { label: 'Active Users', value: k.active_users.toLocaleString(), icon: 'pi-user-plus', color: '#34a853', delta: `${activePercent}% of total` },
    { label: 'Avg Check', value: `${Math.round(k.avg_check).toLocaleString()} \u20BD`, icon: 'pi-wallet', color: '#fbbc04', delta: null },
    { label: 'Conversion', value: `${k.conversion_rate}%`, icon: 'pi-chart-line', color: '#ea4335', delta: null },
    { label: 'Retention', value: `${k.retention_rate}%`, icon: 'pi-replay', color: '#ab47bc', delta: null },
  ]
})

// ── Segment distribution bar chart ──

const segmentBarOption = computed(() => {
  if (!userStats.value?.by_segment?.length) return null
  const sorted = [...userStats.value.by_segment].sort((a, b) => b.count - a.count)
  const colors = ['#1a73e8', '#34a853', '#fbbc04', '#ea4335', '#ab47bc', '#ff6d01', '#00bcd4', '#795548']
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        const p = params[0]
        const seg = sorted[p.dataIndex]
        return `<b>${seg.segment}</b><br/>Users: ${seg.count.toLocaleString()}<br/>Avg Check: ${Math.round(seg.avg_check).toLocaleString()} \u20BD`
      }
    },
    grid: { left: 16, right: 24, top: 12, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: sorted.map(s => s.segment.length > 16 ? s.segment.slice(0, 14) + '\u2026' : s.segment),
      axisLabel: { fontSize: 11, color: '#8c8c8c', rotate: sorted.length > 5 ? 25 : 0 },
      axisLine: { lineStyle: { color: '#e8e8e8' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLabel: { fontSize: 10, color: '#8c8c8c', formatter: (v: number) => v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v },
      splitLine: { lineStyle: { color: '#f0f0f0', type: 'dashed' } },
    },
    series: [{
      type: 'bar',
      data: sorted.map((s, i) => ({
        value: s.count,
        itemStyle: { color: colors[i % colors.length], borderRadius: [4, 4, 0, 0] },
      })),
      barMaxWidth: 40,
      emphasis: { itemStyle: { opacity: 0.85 } },
    }],
  }
})

// ── Audience by segment (pie) ──

const segmentPieOption = computed(() => {
  if (!userStats.value?.by_segment?.length) return null
  const colors = ['#1a73e8', '#34a853', '#fbbc04', '#ea4335', '#ab47bc', '#ff6d01']
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 11, color: '#8c8c8c' }, itemWidth: 10, itemHeight: 10 },
    series: [{
      type: 'pie',
      radius: ['38%', '64%'],
      center: ['50%', '42%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 13, fontWeight: 600 } },
      data: userStats.value.by_segment.map((s, i) => ({
        name: s.segment,
        value: s.count,
        itemStyle: { color: colors[i % colors.length] },
      })),
    }],
  }
})

// ── Campaign performance (line + bar) ──

const perfChartOption = computed(() => {
  if (!campaignPerformance.value.length) return null
  const dates = campaignPerformance.value.map(m => m.date.slice(5))
  return {
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, textStyle: { fontSize: 11, color: '#8c8c8c' } },
    grid: { left: 12, right: 12, top: 24, bottom: 40, containLabel: true },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10, color: '#8c8c8c' } },
    yAxis: [
      { type: 'value', name: 'Count', axisLabel: { fontSize: 10, color: '#8c8c8c' }, splitLine: { lineStyle: { color: '#f0f0f0', type: 'dashed' } } },
      { type: 'value', name: 'Rate %', axisLabel: { fontSize: 10, color: '#8c8c8c' }, splitLine: { show: false } },
    ],
    series: [
      { name: 'Impressions', type: 'bar', data: campaignPerformance.value.map(m => m.impressions), itemStyle: { color: '#1a73e8', borderRadius: [3, 3, 0, 0] }, barMaxWidth: 20 },
      { name: 'Clicks', type: 'bar', data: campaignPerformance.value.map(m => m.clicks), itemStyle: { color: '#34a853', borderRadius: [3, 3, 0, 0] }, barMaxWidth: 20 },
      { name: 'CTR %', type: 'line', yAxisIndex: 1, data: campaignPerformance.value.map(m => m.ctr), lineStyle: { color: '#ea4335', width: 2 }, itemStyle: { color: '#ea4335' }, smooth: true },
    ],
  }
})

// ── Avg check by segment (horizontal bar) ──

const avgCheckOption = computed(() => {
  if (!userStats.value?.by_segment?.length) return null
  const sorted = [...userStats.value.by_segment].sort((a, b) => b.avg_check - a.avg_check)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: (params: any) => `${params[0].name}: ${Math.round(params[0].value).toLocaleString()} \u20BD` },
    grid: { left: 12, right: 24, top: 8, bottom: 4, containLabel: true },
    xAxis: { type: 'value', axisLabel: { fontSize: 10, color: '#8c8c8c' }, splitLine: { lineStyle: { color: '#f0f0f0', type: 'dashed' } } },
    yAxis: {
      type: 'category',
      data: sorted.map(s => s.segment.length > 22 ? s.segment.slice(0, 20) + '\u2026' : s.segment).reverse(),
      axisLabel: { fontSize: 10, color: '#8c8c8c' },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [{
      type: 'bar',
      data: sorted.map(s => Math.round(s.avg_check)).reverse(),
      barMaxWidth: 20,
      itemStyle: { color: '#fbbc04', borderRadius: [0, 4, 4, 0] },
    }],
  }
})

// ── Execution log (merged + sorted) ──

interface LogEntry {
  id: string
  type: 'scenario' | 'conversation'
  title: string
  preview: string | null
  status: string
  date: string
  meta: string
}

const executionLog = computed<LogEntry[]>(() => {
  const entries: LogEntry[] = []

  for (const s of scenarios.value) {
    const stepsInfo = s.summary
      ? `${s.summary.completed ?? 0}/${s.summary.total_steps ?? 0} steps`
      : ''
    entries.push({
      id: `s-${s.id}`,
      type: 'scenario',
      title: s.query.length > 80 ? s.query.slice(0, 78) + '\u2026' : s.query,
      preview: null,
      status: s.status,
      date: s.created_at,
      meta: stepsInfo,
    })
  }

  for (const c of conversations.value) {
    entries.push({
      id: `c-${c.id}`,
      type: 'conversation',
      title: c.title,
      preview: c.preview,
      status: 'completed',
      date: c.updated_at,
      meta: `${c.message_count} messages`,
    })
  }

  // Sort by date descending
  entries.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
  return entries
})

const filteredLog = computed(() => {
  if (activeLogTab.value === 'all') return executionLog.value
  if (activeLogTab.value === 'scenarios') return executionLog.value.filter(e => e.type === 'scenario')
  return executionLog.value.filter(e => e.type === 'conversation')
})

// ── Status helpers ──

const statusColor: Record<string, string> = {
  completed: '#34a853',
  active: '#1a73e8',
  draft: '#8c8c8c',
  scheduled: '#fbbc04',
  ready: '#34a853',
  building: '#1a73e8',
  running: '#1a73e8',
  error: '#ea4335',
  cancelled: '#8c8c8c',
}

function formatRelativeDate(d: string) {
  const now = new Date()
  const date = new Date(d)
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  const diffHr = Math.floor(diffMs / 3600000)
  const diffDay = Math.floor(diffMs / 86400000)

  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHr < 24) return `${diffHr}h ago`
  if (diffDay < 7) return `${diffDay}d ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
</script>

<template>
  <div class="dashboard-view">
    <div class="dashboard-container">

      <!-- ── Header ── -->
      <div class="dash-header">
        <div>
          <h1 class="dash-title">{{ t('nav.dashboard') }}</h1>
          <p class="dash-subtitle">Live metrics from connected APIs</p>
        </div>
        <button class="refresh-btn" @click="fetchDashboard" :disabled="isLoading" title="Refresh data">
          <i class="pi pi-refresh" :class="{ 'pi-spin': isLoading }"></i>
        </button>
      </div>

      <!-- ── Loading skeleton ── -->
      <div v-if="isLoading" class="dash-loading">
        <div class="kpi-row">
          <div v-for="i in 5" :key="i" class="kpi-card skeleton-card">
            <div class="skeleton" style="width:48px;height:48px;border-radius:12px"></div>
            <div style="flex:1">
              <div class="skeleton" style="width:72px;height:11px;margin-bottom:8px"></div>
              <div class="skeleton" style="width:96px;height:24px"></div>
            </div>
          </div>
        </div>
        <div class="charts-row">
          <div class="chart-card"><div class="skeleton" style="height:280px;border-radius:8px"></div></div>
          <div class="chart-card"><div class="skeleton" style="height:280px;border-radius:8px"></div></div>
        </div>
        <div class="log-card">
          <div v-for="i in 4" :key="i" style="padding:14px 0;display:flex;gap:12px;align-items:center">
            <div class="skeleton" style="width:8px;height:8px;border-radius:50%"></div>
            <div style="flex:1"><div class="skeleton" style="width:60%;height:13px;margin-bottom:6px"></div><div class="skeleton" style="width:30%;height:10px"></div></div>
          </div>
        </div>
      </div>

      <!-- ── Error ── -->
      <div v-else-if="error" class="dash-state-card">
        <i class="pi pi-exclamation-triangle" style="font-size:40px;color:#ea4335"></i>
        <p style="color:#5f6368;margin:8px 0 0">{{ error }}</p>
        <button @click="fetchDashboard" class="action-btn primary" style="margin-top:16px">Retry</button>
      </div>

      <!-- ── Empty ── -->
      <div v-else-if="!hasData" class="dash-state-card">
        <i class="pi pi-chart-bar" style="font-size:48px;color:#dadce0"></i>
        <h2 style="font-size:20px;color:#202124;margin:12px 0 0">No data yet</h2>
        <p style="font-size:14px;color:#5f6368;margin:4px 0 0">Upload a Swagger spec and run queries to populate the dashboard.</p>
        <router-link to="/swagger" class="action-btn primary" style="margin-top:16px;text-decoration:none">Upload API Spec</router-link>
      </div>

      <!-- ── Main content ── -->
      <template v-else>

        <!-- KPI Cards -->
        <div class="kpi-row" v-if="kpiCards.length">
          <div v-for="card in kpiCards" :key="card.label" class="kpi-card">
            <div class="kpi-icon" :style="{ background: card.color + '14', color: card.color }">
              <i class="pi" :class="card.icon"></i>
            </div>
            <div class="kpi-info">
              <span class="kpi-label">{{ card.label }}</span>
              <span class="kpi-value">{{ card.value }}</span>
              <span v-if="card.delta" class="kpi-delta">{{ card.delta }}</span>
            </div>
          </div>
        </div>

        <!-- Charts row: Segment distribution + Pie -->
        <div class="charts-row">
          <div class="chart-card" v-if="segmentBarOption">
            <h3 class="card-title"><i class="pi pi-chart-bar"></i> Segment Distribution</h3>
            <v-chart :option="segmentBarOption" autoresize style="height:280px" />
          </div>
          <div class="chart-card" v-if="segmentPieOption">
            <h3 class="card-title"><i class="pi pi-users"></i> Audience Share</h3>
            <v-chart :option="segmentPieOption" autoresize style="height:280px" />
          </div>
        </div>

        <!-- Avg check chart (full-width if data) -->
        <div class="chart-card" v-if="avgCheckOption" style="width:100%">
          <h3 class="card-title"><i class="pi pi-wallet"></i> Avg Check by Segment</h3>
          <v-chart :option="avgCheckOption" autoresize style="height:260px" />
        </div>

        <!-- Campaign Performance -->
        <div class="chart-card" v-if="perfChartOption" style="width:100%">
          <h3 class="card-title"><i class="pi pi-chart-line"></i> Campaign Performance<template v-if="campaigns.length"> &mdash; {{ campaigns[0]?.title }}</template></h3>
          <v-chart :option="perfChartOption" autoresize style="height:300px" />
        </div>

        <!-- Segment Cards -->
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
                <span class="entity-badge" :style="{ background: statusColor[seg.status] || '#8c8c8c' }">{{ seg.status }}</span>
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
                <span class="entity-badge" :style="{ background: statusColor[camp.status] || '#8c8c8c' }">{{ camp.status }}</span>
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

        <!-- ── Execution Log ── -->
        <div class="section">
          <h3 class="section-title"><i class="pi pi-history"></i> Execution Log</h3>

          <!-- Tabs -->
          <div class="log-tabs">
            <button
              class="log-tab"
              :class="{ active: activeLogTab === 'all' }"
              @click="activeLogTab = 'all'"
            >All<span class="tab-count">{{ executionLog.length }}</span></button>
            <button
              class="log-tab"
              :class="{ active: activeLogTab === 'scenarios' }"
              @click="activeLogTab = 'scenarios'"
            >Scenarios<span class="tab-count">{{ scenarios.length }}</span></button>
            <button
              class="log-tab"
              :class="{ active: activeLogTab === 'conversations' }"
              @click="activeLogTab = 'conversations'"
            >Conversations<span class="tab-count">{{ conversations.length }}</span></button>
          </div>

          <div class="log-card" v-if="filteredLog.length">
            <div
              v-for="entry in filteredLog"
              :key="entry.id"
              class="log-row"
            >
              <div class="log-status-dot" :style="{ background: statusColor[entry.status] || '#8c8c8c' }"></div>
              <div class="log-type-badge" :class="entry.type">
                <i :class="entry.type === 'scenario' ? 'pi pi-share-alt' : 'pi pi-comment'"></i>
              </div>
              <div class="log-content">
                <div class="log-title">{{ entry.title }}</div>
                <div class="log-meta-row">
                  <span class="log-status-text" :style="{ color: statusColor[entry.status] || '#8c8c8c' }">{{ entry.status }}</span>
                  <span v-if="entry.meta" class="log-meta-sep">&middot;</span>
                  <span v-if="entry.meta" class="log-meta-text">{{ entry.meta }}</span>
                </div>
              </div>
              <div class="log-time">{{ formatRelativeDate(entry.date) }}</div>
            </div>
          </div>
          <div v-else class="log-empty">
            <i class="pi pi-inbox"></i>
            <span>No activity yet. Run a query in Chat to get started.</span>
          </div>
        </div>

      </template>
    </div>
  </div>
</template>

<style scoped>
/* ── Layout ── */
.dashboard-view {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
  background: var(--color-bg-secondary, #f8f9fa);
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
  color: var(--color-text-primary, #202124);
  margin: 0;
}

.dash-subtitle {
  font-size: 13px;
  color: var(--color-text-tertiary, #80868b);
  margin: 4px 0 0;
}

.refresh-btn {
  width: 36px;
  height: 36px;
  border: 1px solid var(--color-border, #dadce0);
  border-radius: 8px;
  background: var(--color-bg, #fff);
  color: var(--color-text-secondary, #5f6368);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.refresh-btn:hover { background: var(--color-bg-tertiary, #f1f3f4); }
.refresh-btn:disabled { opacity: 0.5; cursor: default; }

/* ── KPI Row ── */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}

.kpi-card {
  background: var(--color-bg, #fff);
  border: 1px solid var(--color-border-light, #e8eaed);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  gap: 12px;
  align-items: center;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  transition: box-shadow 0.15s, transform 0.15s;
}

.kpi-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  transform: translateY(-1px);
}

.kpi-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
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
  font-weight: 600;
  color: var(--color-text-tertiary, #80868b);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text-primary, #202124);
  line-height: 1.25;
}

.kpi-delta {
  font-size: 11px;
  color: #34a853;
  font-weight: 500;
  margin-top: 1px;
}

/* ── Charts ── */
.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.chart-card {
  background: var(--color-bg, #fff);
  border: 1px solid var(--color-border-light, #e8eaed);
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary, #202124);
  margin: 0 0 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title i {
  font-size: 14px;
  color: var(--color-accent, #1a73e8);
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
  color: var(--color-text-primary, #202124);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-title i {
  font-size: 16px;
  color: var(--color-accent, #1a73e8);
}

/* ── Entity Cards ── */
.entity-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.entity-card {
  background: var(--color-bg, #fff);
  border: 1px solid var(--color-border-light, #e8eaed);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  transition: all 0.15s;
}

.entity-card.clickable { cursor: pointer; }
.entity-card.clickable:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); border-color: var(--color-accent, #1a73e8); }
.entity-card.active { border-color: var(--color-accent, #1a73e8); box-shadow: 0 0 0 1px var(--color-accent, #1a73e8); }

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
  color: var(--color-text-primary, #202124);
}

.entity-badge {
  font-size: 10px;
  font-weight: 600;
  color: white;
  padding: 2px 8px;
  border-radius: 100px;
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
  color: var(--color-accent, #1a73e8);
}

.metric-label {
  font-size: 11px;
  color: var(--color-text-tertiary, #80868b);
}

.entity-desc {
  font-size: 12px;
  color: var(--color-text-secondary, #5f6368);
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
  border-top: 1px solid var(--color-border-light, #e8eaed);
}

.detail-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-tertiary, #80868b);
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
  color: var(--color-text-tertiary, #80868b);
  font-family: var(--font-mono, 'JetBrains Mono', monospace);
  min-width: 120px;
}

.detail-val {
  color: var(--color-text-primary, #202124);
  font-weight: 500;
}

/* ── Campaign specifics ── */
.campaign-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--color-text-secondary, #5f6368);
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
  padding: 8px 6px;
  background: var(--color-bg-secondary, #f8f9fa);
  border-radius: 8px;
}

.mini-val {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-text-primary, #202124);
}

.mini-label {
  font-size: 9px;
  color: var(--color-text-tertiary, #80868b);
  text-transform: uppercase;
  letter-spacing: 0.2px;
}

/* ── Variants ── */
.variant-card {
  background: var(--color-bg-secondary, #f8f9fa);
  border-radius: 8px;
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
  background: var(--color-accent, #1a73e8);
  color: white;
  padding: 1px 6px;
  border-radius: 4px;
}

.variant-weight {
  font-size: 11px;
  color: var(--color-text-tertiary, #80868b);
}

.variant-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary, #202124);
  margin-bottom: 2px;
}

.variant-body {
  font-size: 12px;
  color: var(--color-text-secondary, #5f6368);
  line-height: 1.4;
}

/* ── Execution Log ── */
.log-tabs {
  display: flex;
  gap: 4px;
  background: var(--color-bg-tertiary, #f1f3f4);
  padding: 3px;
  border-radius: 10px;
  width: fit-content;
}

.log-tab {
  padding: 6px 14px;
  border: none;
  background: transparent;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-secondary, #5f6368);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.15s;
}

.log-tab:hover { color: var(--color-text-primary, #202124); }
.log-tab.active {
  background: var(--color-bg, #fff);
  color: var(--color-text-primary, #202124);
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.tab-count {
  font-size: 11px;
  font-weight: 600;
  background: var(--color-bg-secondary, #f8f9fa);
  color: var(--color-text-tertiary, #80868b);
  padding: 0 6px;
  border-radius: 100px;
  min-width: 18px;
  text-align: center;
}

.log-tab.active .tab-count {
  background: var(--color-accent, #1a73e8);
  color: white;
}

.log-card {
  background: var(--color-bg, #fff);
  border: 1px solid var(--color-border-light, #e8eaed);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  overflow: hidden;
}

.log-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border-light, #e8eaed);
  transition: background 0.1s;
}

.log-row:last-child { border-bottom: none; }
.log-row:hover { background: var(--color-bg-secondary, #f8f9fa); }

.log-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.log-type-badge {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 12px;
}

.log-type-badge.scenario {
  background: #e8f0fe;
  color: #1a73e8;
}

.log-type-badge.conversation {
  background: #e6f4ea;
  color: #34a853;
}

.log-content {
  flex: 1;
  min-width: 0;
}

.log-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary, #202124);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.log-meta-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  margin-top: 2px;
}

.log-status-text {
  font-weight: 600;
  text-transform: capitalize;
}

.log-meta-sep {
  color: var(--color-text-tertiary, #80868b);
}

.log-meta-text {
  color: var(--color-text-tertiary, #80868b);
}

.log-time {
  font-size: 11px;
  color: var(--color-text-tertiary, #80868b);
  white-space: nowrap;
  flex-shrink: 0;
}

.log-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 32px 16px;
  background: var(--color-bg, #fff);
  border: 1px solid var(--color-border-light, #e8eaed);
  border-radius: 12px;
  color: var(--color-text-tertiary, #80868b);
  font-size: 13px;
}

.log-empty i {
  font-size: 20px;
}

/* ── States ── */
.dash-state-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  background: var(--color-bg, #fff);
  border: 1px solid var(--color-border-light, #e8eaed);
  border-radius: 12px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  padding: 8px 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.action-btn.primary {
  background: var(--color-accent, #1a73e8);
  color: white;
}

.action-btn.primary:hover {
  background: var(--color-accent-hover, #1765cc);
}

/* ── Skeleton ── */
.skeleton-card { justify-content: flex-start; }
.skeleton {
  background: linear-gradient(90deg, var(--color-bg-secondary, #f8f9fa) 25%, var(--color-border-light, #e8eaed) 50%, var(--color-bg-secondary, #f8f9fa) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
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

  .log-tabs { width: 100%; }
  .log-tab { flex: 1; justify-content: center; font-size: 12px; padding: 6px 8px; }
}

@media (max-width: 480px) {
  .kpi-row { grid-template-columns: 1fr; }
  .kpi-card { padding: 12px; }
  .kpi-value { font-size: 18px; }
  .kpi-icon { width: 36px; height: 36px; font-size: 15px; border-radius: 10px; }
  .dash-title { font-size: 20px; }
}
</style>
