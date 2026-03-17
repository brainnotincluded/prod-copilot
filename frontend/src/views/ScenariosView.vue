<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { VueFlow, useVueFlow, Position, MarkerType } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'
import { useLocale } from '@/composables/useLocale'
import { useAuth } from '@/composables/useAuth'

const { t } = useLocale()
const { getAuthHeaders } = useAuth()
const { fitView } = useVueFlow()
const router = useRouter()

// ──────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────

type ScenarioStatus = 'running' | 'completed' | 'error' | 'cancelled'
type StepStatus = 'pending' | 'running' | 'completed' | 'error' | 'skipped'
type ConfirmationStatus = 'pending' | 'approved' | 'rejected'
type NodeActionType = 'api_call' | 'data_process' | 'execute_code' | 'format_output'

interface Scenario {
  id: number
  correlation_id: string
  query: string
  status: ScenarioStatus
  graph_nodes: number
  graph_edges: number
  summary: string | null
  created_at: string
  finished_at: string | null
}

interface ScenarioStep {
  id: number
  step_number: number
  action: NodeActionType
  description: string
  status: StepStatus
  endpoint_method: string | null
  endpoint_path: string | null
  request_payload: any
  response_data: any
  reasoning: string | null
  alternatives: string[] | null
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  error_message: string | null
  confirmation_status: ConfirmationStatus | null
}

interface GraphNode {
  id: string
  label: string
  action: NodeActionType
  status: StepStatus
  step_number: number
  position?: { x: number; y: number }
}

interface GraphEdge {
  id: string
  source: string
  target: string
  label?: string
}

interface GraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
  layout: string
  direction: string
}

// ──────────────────────────────────────────────
// State
// ──────────────────────────────────────────────

const scenarios = ref<Scenario[]>([])
const selectedScenario = ref<Scenario | null>(null)
const scenarioSteps = ref<ScenarioStep[]>([])
const graphData = ref<GraphResponse | null>(null)
const selectedStep = ref<ScenarioStep | null>(null)

const isLoadingList = ref(false)
const isLoadingDetail = ref(false)
const statusFilter = ref<'all' | ScenarioStatus>('all')

const isMobile = ref(false)

function checkMobile() {
  isMobile.value = window.innerWidth < 768
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  fetchScenarios()
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})

// ──────────────────────────────────────────────
// API helpers
// ──────────────────────────────────────────────

async function apiFetch<T>(url: string): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...getAuthHeaders(),
  }
  const resp = await fetch(url, { headers })
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`)
  }
  return resp.json()
}

// ──────────────────────────────────────────────
// Fetch scenarios list
// ──────────────────────────────────────────────

async function fetchScenarios() {
  isLoadingList.value = true
  try {
    scenarios.value = await apiFetch<Scenario[]>('/api/v1/scenarios')
  } catch {
    scenarios.value = []
  } finally {
    isLoadingList.value = false
  }
}

// ──────────────────────────────────────────────
// Filtered scenarios
// ──────────────────────────────────────────────

const filteredScenarios = computed(() => {
  if (statusFilter.value === 'all') return scenarios.value
  return scenarios.value.filter((s) => s.status === statusFilter.value)
})

const statusCounts = computed(() => {
  const counts: Record<string, number> = { all: scenarios.value.length }
  for (const s of scenarios.value) {
    counts[s.status] = (counts[s.status] || 0) + 1
  }
  return counts
})

// ──────────────────────────────────────────────
// Select a scenario
// ──────────────────────────────────────────────

async function selectScenario(scenario: Scenario) {
  selectedScenario.value = scenario
  selectedStep.value = null
  isLoadingDetail.value = true

  try {
    const [steps, graph] = await Promise.all([
      apiFetch<ScenarioStep[]>(`/api/v1/scenarios/${scenario.id}/steps`),
      apiFetch<GraphResponse>(`/api/v1/scenarios/${scenario.id}/graph`),
    ])
    scenarioSteps.value = steps
    graphData.value = graph
    await nextTick()
    setTimeout(() => fitView({ padding: 0.2 }), 200)
  } catch {
    scenarioSteps.value = []
    graphData.value = null
  } finally {
    isLoadingDetail.value = false
  }
}

function goBack() {
  selectedScenario.value = null
  selectedStep.value = null
  scenarioSteps.value = []
  graphData.value = null
}

// ──────────────────────────────────────────────
// Graph nodes & edges for Vue Flow
// ──────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  completed: '#34a853',
  running: '#1a73e8',
  error: '#ea4335',
  pending: '#9e9e9e',
  skipped: '#9e9e9e',
}

const ACTION_ICONS: Record<NodeActionType, string> = {
  api_call: 'pi-server',
  data_process: 'pi-database',
  execute_code: 'pi-code',
  format_output: 'pi-file-export',
}

const NODE_WIDTH = 200
const NODE_HEIGHT = 60
const VERTICAL_GAP = 100
const HORIZONTAL_GAP = 260

const flowNodes = computed(() => {
  if (!graphData.value) return []
  return graphData.value.nodes.map((n, index) => {
    const fallbackX = (index % 3) * HORIZONTAL_GAP + 50
    const fallbackY = Math.floor(index / 3) * VERTICAL_GAP + 50
    return {
      id: n.id,
      type: 'scenarioStep',
      position: n.position || { x: fallbackX, y: fallbackY },
      data: {
        label: n.label,
        action: n.action,
        status: n.status,
        step_number: n.step_number,
        statusColor: STATUS_COLORS[n.status] || '#9e9e9e',
        icon: ACTION_ICONS[n.action] || 'pi-cog',
      },
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
    }
  })
})

const flowEdges = computed(() => {
  if (!graphData.value) return []
  return graphData.value.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    type: 'smoothstep',
    animated: selectedScenario.value?.status === 'running',
    label: e.label || '',
    labelStyle: { fontSize: '10px', fill: 'var(--color-text-secondary)', fontWeight: 500 },
    labelBgStyle: { fill: 'var(--color-bg)', fillOpacity: 0.9 },
    labelBgPadding: [3, 5] as [number, number],
    style: { stroke: 'var(--color-border)', strokeWidth: 2 },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: 'var(--color-text-tertiary)',
      width: 12,
      height: 12,
    },
  }))
})

// ──────────────────────────────────────────────
// Node click -> step selection
// ──────────────────────────────────────────────

function onNodeClick({ node }: { node: any }) {
  if (node.type !== 'scenarioStep') return
  const stepNum = node.data.step_number
  const step = scenarioSteps.value.find((s) => s.step_number === stepNum)
  if (step) {
    selectedStep.value = step
  }
}

function closeStepDetail() {
  selectedStep.value = null
}

// ──────────────────────────────────────────────
// Formatting helpers
// ──────────────────────────────────────────────

function formatDate(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const days = Math.floor(diff / 86400000)
  if (days === 0) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days}d ago`
  return d.toLocaleDateString()
}

function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

function formatJson(obj: any): string {
  if (!obj) return ''
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

function statusIcon(status: string): string {
  switch (status) {
    case 'completed': return 'pi-check-circle'
    case 'running': return 'pi-spin pi-spinner'
    case 'error': return 'pi-times-circle'
    case 'cancelled': return 'pi-ban'
    case 'pending': return 'pi-clock'
    case 'skipped': return 'pi-minus-circle'
    default: return 'pi-circle'
  }
}

function confirmationIcon(status: ConfirmationStatus): string {
  switch (status) {
    case 'approved': return 'pi-check'
    case 'rejected': return 'pi-times'
    case 'pending': return 'pi-clock'
    default: return 'pi-circle'
  }
}

function confirmationLabel(status: ConfirmationStatus): string {
  switch (status) {
    case 'approved': return t('scenarios.approved')
    case 'rejected': return t('scenarios.rejected')
    case 'pending': return t('scenarios.pending')
    default: return status
  }
}

// VueFlow interaction options
const panOnScroll = computed(() => !isMobile.value)
</script>

<template>
  <div class="scenarios-view">
    <!-- Left Panel: Scenario list -->
    <aside
      class="scenarios-list-panel"
      :class="{ hidden: isMobile && selectedScenario }"
    >
      <div class="panel-header">
        <h2 class="panel-title">{{ t('scenarios.title') }}</h2>
        <button class="refresh-btn" @click="fetchScenarios" title="Refresh">
          <i class="pi pi-refresh" :class="{ 'pi-spin': isLoadingList }"></i>
        </button>
      </div>
      <p class="panel-description">{{ t('scenarios.description') }}</p>

      <!-- Status filter tabs -->
      <div class="status-filters">
        <button
          v-for="filter in (['all', 'running', 'completed', 'error', 'cancelled'] as const)"
          :key="filter"
          class="filter-btn"
          :class="{ active: statusFilter === filter }"
          @click="statusFilter = filter"
        >
          <span class="filter-label">
            {{ filter === 'all' ? t('scenarios.filterAll') : t(`scenarios.${filter}`) }}
          </span>
          <span v-if="statusCounts[filter]" class="filter-count">{{ statusCounts[filter] }}</span>
        </button>
      </div>

      <!-- Loading -->
      <div v-if="isLoadingList" class="list-loading">
        <i class="pi pi-spin pi-spinner"></i>
        <span>{{ t('scenarios.loading') }}</span>
      </div>

      <!-- Empty state -->
      <div v-else-if="filteredScenarios.length === 0" class="list-empty">
        <i class="pi pi-sitemap list-empty-icon"></i>
        <p class="list-empty-text">{{ t('scenarios.empty') }}</p>
        <p class="list-empty-hint">{{ t('scenarios.emptyHint') }}</p>
        <button class="goto-chat-btn" @click="router.push('/chat')">
          <i class="pi pi-comments"></i>
          {{ t('scenarios.goToChat') }}
        </button>
      </div>

      <!-- Scenario cards -->
      <div v-else class="scenario-cards">
        <div
          v-for="scenario in filteredScenarios"
          :key="scenario.id"
          class="scenario-card"
          :class="{ selected: selectedScenario?.id === scenario.id }"
          @click="selectScenario(scenario)"
        >
          <div class="card-top">
            <span
              class="status-dot"
              :class="`status-${scenario.status}`"
            ></span>
            <span class="card-query">{{ scenario.query }}</span>
          </div>
          <div class="card-meta">
            <span class="card-status">
              <i class="pi" :class="statusIcon(scenario.status)"></i>
              {{ t(`scenarios.${scenario.status}`) }}
            </span>
            <span class="card-nodes">{{ scenario.graph_nodes }} {{ t('scenarios.steps') }}</span>
            <span class="card-date">{{ formatDate(scenario.created_at) }}</span>
          </div>
          <p v-if="scenario.summary" class="card-summary">{{ scenario.summary }}</p>
        </div>
      </div>
    </aside>

    <!-- Right Panel: Detail / Graph -->
    <main
      class="scenarios-detail-panel"
      :class="{ hidden: isMobile && !selectedScenario }"
    >
      <!-- No selection state -->
      <div v-if="!selectedScenario" class="detail-empty">
        <i class="pi pi-sitemap detail-empty-icon"></i>
        <p>{{ t('scenarios.description') }}</p>
      </div>

      <!-- Loading detail -->
      <div v-else-if="isLoadingDetail" class="detail-loading">
        <i class="pi pi-spin pi-spinner"></i>
        <span>{{ t('scenarios.loading') }}</span>
      </div>

      <!-- Scenario detail content -->
      <div v-else class="detail-content">
        <!-- Detail header -->
        <div class="detail-header">
          <button v-if="isMobile" class="back-btn" @click="goBack">
            <i class="pi pi-arrow-left"></i>
          </button>
          <div class="detail-header-info">
            <h3 class="detail-title">{{ selectedScenario.query }}</h3>
            <div class="detail-header-meta">
              <span class="status-badge" :class="`status-${selectedScenario.status}`">
                <i class="pi" :class="statusIcon(selectedScenario.status)"></i>
                {{ t(`scenarios.${selectedScenario.status}`) }}
              </span>
              <span class="meta-separator">|</span>
              <span class="meta-text">{{ scenarioSteps.length }} {{ t('scenarios.steps') }}</span>
              <span v-if="selectedScenario.finished_at" class="meta-separator">|</span>
              <span v-if="selectedScenario.finished_at" class="meta-text">
                {{ formatDate(selectedScenario.finished_at) }}
              </span>
            </div>
          </div>
          <button v-if="!isMobile" class="close-detail-btn" @click="goBack" :title="t('common.close')">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <!-- Execution Graph -->
        <div class="graph-section">
          <h4 class="section-heading">
            <i class="pi pi-share-alt"></i>
            {{ t('scenarios.graph') }}
          </h4>

          <div v-if="!graphData || flowNodes.length === 0" class="graph-empty">
            <p>{{ t('scenarios.noGraph') }}</p>
          </div>
          <div v-else class="graph-container">
            <VueFlow
              :nodes="flowNodes"
              :edges="flowEdges"
              :default-viewport="{ zoom: 0.85, x: 50, y: 30 }"
              :min-zoom="0.2"
              :max-zoom="2"
              :pan-on-scroll="panOnScroll"
              :zoom-on-pinch="true"
              :zoom-on-double-click="false"
              :prevent-scrolling="true"
              @node-click="onNodeClick"
              fit-view-on-init
            >
              <template #node-scenarioStep="{ data }">
                <div
                  class="flow-node"
                  :class="[
                    `node-status-${data.status}`,
                    { 'node-selected': selectedStep?.step_number === data.step_number }
                  ]"
                  :style="{ borderColor: data.statusColor }"
                >
                  <div class="flow-node-header">
                    <i class="pi" :class="data.icon" :style="{ color: data.statusColor }"></i>
                    <span class="flow-node-number">#{{ data.step_number }}</span>
                  </div>
                  <div class="flow-node-label">{{ data.label }}</div>
                </div>
              </template>
              <Background :gap="16" :size="1" />
              <Controls :show-interactive="false" />
              <MiniMap
                v-if="!isMobile"
                :node-stroke-width="3"
                :pannable="true"
                :zoomable="true"
              />
            </VueFlow>
          </div>
        </div>

        <!-- Step Details Panel -->
        <transition name="step-slide">
          <div v-if="selectedStep" class="step-detail">
            <div class="step-detail-header">
              <div class="step-title-row">
                <span class="step-number">#{{ selectedStep.step_number }}</span>
                <span class="step-action-badge" :class="`action-${selectedStep.action}`">
                  <i class="pi" :class="ACTION_ICONS[selectedStep.action] || 'pi-cog'"></i>
                  {{ selectedStep.action.replace('_', ' ') }}
                </span>
                <span
                  class="step-status-badge"
                  :class="`status-${selectedStep.status}`"
                >
                  <i class="pi" :class="statusIcon(selectedStep.status)"></i>
                  {{ selectedStep.status }}
                </span>
                <span
                  v-if="selectedStep.confirmation_status"
                  class="confirmation-badge"
                  :class="`confirm-${selectedStep.confirmation_status}`"
                >
                  <i class="pi" :class="confirmationIcon(selectedStep.confirmation_status)"></i>
                  {{ confirmationLabel(selectedStep.confirmation_status) }}
                </span>
              </div>
              <button class="close-step-btn" @click="closeStepDetail" :title="t('common.close')">
                <i class="pi pi-times"></i>
              </button>
            </div>

            <div class="step-detail-body">
              <!-- Description -->
              <p class="step-description">{{ selectedStep.description }}</p>

              <!-- Duration -->
              <div v-if="selectedStep.duration_ms !== null" class="step-info-row">
                <span class="info-label">
                  <i class="pi pi-clock"></i>
                  {{ t('scenarios.duration') }}
                </span>
                <span class="info-value">{{ formatDuration(selectedStep.duration_ms) }}</span>
              </div>

              <!-- Endpoint -->
              <div v-if="selectedStep.endpoint_method && selectedStep.endpoint_path" class="step-info-row">
                <span class="info-label">
                  <i class="pi pi-server"></i>
                  Endpoint
                </span>
                <span class="info-value endpoint-value">
                  <span class="method-pill" :class="`method-${selectedStep.endpoint_method?.toLowerCase()}`">
                    {{ selectedStep.endpoint_method }}
                  </span>
                  <code>{{ selectedStep.endpoint_path }}</code>
                </span>
              </div>

              <!-- Error message -->
              <div v-if="selectedStep.error_message" class="step-section step-error-section">
                <h5 class="step-section-title error-title">
                  <i class="pi pi-exclamation-triangle"></i>
                  Error
                </h5>
                <pre class="step-code error-code">{{ selectedStep.error_message }}</pre>
              </div>

              <!-- Reasoning (Chain of Thought) -->
              <div v-if="selectedStep.reasoning" class="step-section">
                <h5 class="step-section-title">
                  <i class="pi pi-lightbulb"></i>
                  {{ t('scenarios.reasoning') }}
                </h5>
                <div class="reasoning-box">{{ selectedStep.reasoning }}</div>
              </div>

              <!-- Alternatives considered -->
              <div v-if="selectedStep.alternatives && selectedStep.alternatives.length > 0" class="step-section">
                <h5 class="step-section-title">
                  <i class="pi pi-list"></i>
                  {{ t('scenarios.alternatives') }}
                </h5>
                <ul class="alternatives-list">
                  <li v-for="(alt, idx) in selectedStep.alternatives" :key="idx">
                    {{ alt }}
                  </li>
                </ul>
              </div>

              <!-- Request payload -->
              <div v-if="selectedStep.request_payload" class="step-section">
                <h5 class="step-section-title">
                  <i class="pi pi-upload"></i>
                  {{ t('scenarios.request') }}
                </h5>
                <pre class="step-code">{{ formatJson(selectedStep.request_payload) }}</pre>
              </div>

              <!-- Response data -->
              <div v-if="selectedStep.response_data" class="step-section">
                <h5 class="step-section-title">
                  <i class="pi pi-download"></i>
                  {{ t('scenarios.response') }}
                </h5>
                <pre class="step-code">{{ formatJson(selectedStep.response_data) }}</pre>
              </div>
            </div>
          </div>
        </transition>
      </div>
    </main>
  </div>
</template>

<style scoped>
/* ─────────────────────────────────────────────
   Layout
   ───────────────────────────────────────────── */

.scenarios-view {
  display: flex;
  height: 100%;
  overflow: hidden;
  background: var(--color-bg);
}

.scenarios-list-panel {
  width: 360px;
  min-width: 360px;
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-bg);
}

.scenarios-detail-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-bg-secondary);
}

/* ─────────────────────────────────────────────
   List Panel
   ───────────────────────────────────────────── */

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 20px 0;
}

.panel-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
}

.refresh-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: none;
  color: var(--color-text-secondary);
  cursor: pointer;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.refresh-btn:hover {
  color: var(--color-accent);
  background: var(--color-accent-light);
}

.panel-description {
  font-size: 13px;
  color: var(--color-text-secondary);
  padding: 8px 20px 0;
  margin: 0;
  line-height: 1.5;
}

/* ─────────────────────────────────────────────
   Status Filters
   ───────────────────────────────────────────── */

.status-filters {
  display: flex;
  gap: 6px;
  padding: 16px 20px;
  overflow-x: auto;
  flex-shrink: 0;
}

.filter-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  background: var(--color-bg);
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--transition-fast);
}

.filter-btn:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.filter-btn.active {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: #fff;
}

.filter-count {
  background: rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-full);
  padding: 0 6px;
  font-size: 11px;
  line-height: 18px;
  min-width: 18px;
  text-align: center;
}

.filter-btn:not(.active) .filter-count {
  background: var(--color-bg-tertiary);
}

/* ─────────────────────────────────────────────
   Loading / Empty list
   ───────────────────────────────────────────── */

.list-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 48px 20px;
  color: var(--color-text-secondary);
  font-size: 14px;
}

.list-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
  text-align: center;
  flex: 1;
}

.list-empty-icon {
  font-size: 40px;
  color: var(--color-text-tertiary);
  margin-bottom: 16px;
}

.list-empty-text {
  font-size: 15px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin: 0 0 4px;
}

.list-empty-hint {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0 0 20px;
}

.goto-chat-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  border: none;
  border-radius: var(--radius-pill);
  background: var(--color-accent);
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.goto-chat-btn:hover {
  background: var(--color-accent-hover);
}

/* ─────────────────────────────────────────────
   Scenario Cards
   ───────────────────────────────────────────── */

.scenario-cards {
  flex: 1;
  overflow-y: auto;
  padding: 0 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.scenario-card {
  padding: 14px 16px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: background var(--transition-fast), border-color var(--transition-fast);
  background: var(--color-bg);
}

.scenario-card:hover {
  background: var(--color-accent-light);
  border-color: var(--color-accent);
}

.scenario-card.selected {
  background: var(--color-accent-light);
  border-color: var(--color-accent);
  box-shadow: var(--shadow-sm);
}

.card-top {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
  margin-top: 5px;
}

.status-dot.status-completed { background: var(--color-success); }
.status-dot.status-running { background: var(--color-running); animation: pulse 1.5s ease-in-out infinite; }
.status-dot.status-error { background: var(--color-error); }
.status-dot.status-cancelled { background: var(--color-text-tertiary); }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.card-query {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.card-status {
  display: flex;
  align-items: center;
  gap: 4px;
}

.card-summary {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ─────────────────────────────────────────────
   Detail Panel
   ───────────────────────────────────────────── */

.detail-empty,
.detail-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: var(--color-text-secondary);
  gap: 12px;
  font-size: 14px;
  padding: 40px;
  text-align: center;
}

.detail-empty-icon {
  font-size: 48px;
  color: var(--color-text-tertiary);
}

.detail-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.detail-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
  flex-shrink: 0;
}

.back-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: none;
  color: var(--color-text-primary);
  cursor: pointer;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.back-btn:hover {
  background: var(--color-bg-tertiary);
}

.detail-header-info {
  flex: 1;
  min-width: 0;
}

.detail-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 4px;
  line-height: 1.4;
}

.detail-header-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.meta-separator {
  color: var(--color-border);
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 500;
}

.status-badge.status-completed {
  background: rgba(52, 168, 83, 0.1);
  color: var(--color-success);
}

.status-badge.status-running {
  background: rgba(26, 115, 232, 0.1);
  color: var(--color-running);
}

.status-badge.status-error {
  background: rgba(234, 67, 53, 0.1);
  color: var(--color-error);
}

.status-badge.status-cancelled {
  background: var(--color-bg-tertiary);
  color: var(--color-text-secondary);
}

.close-detail-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: none;
  color: var(--color-text-secondary);
  cursor: pointer;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.close-detail-btn:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-tertiary);
}

/* ─────────────────────────────────────────────
   Graph Section
   ───────────────────────────────────────────── */

.graph-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.section-heading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
  flex-shrink: 0;
}

.section-heading .pi {
  font-size: 14px;
  color: var(--color-accent);
}

.graph-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: var(--color-text-secondary);
  font-size: 14px;
  padding: 40px;
}

.graph-container {
  flex: 1;
  position: relative;
  margin: 0 12px 12px;
  border-radius: var(--radius-lg);
  overflow: hidden;
  border: 1px solid var(--color-border);
  background: var(--color-bg);
}

/* ─────────────────────────────────────────────
   Vue Flow Custom Node
   ───────────────────────────────────────────── */

.flow-node {
  width: 200px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  border: 2px solid var(--color-border);
  background: var(--color-bg);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: box-shadow var(--transition-fast), border-color var(--transition-fast);
}

.flow-node:hover {
  box-shadow: var(--shadow-md);
}

.flow-node.node-selected {
  box-shadow: var(--shadow-lg);
  border-width: 2px;
}

.flow-node.node-status-completed { border-color: var(--color-success); }
.flow-node.node-status-running { border-color: var(--color-running); }
.flow-node.node-status-error { border-color: var(--color-error); }
.flow-node.node-status-pending { border-color: var(--color-text-tertiary); }
.flow-node.node-status-skipped { border-color: var(--color-text-tertiary); }

.flow-node-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.flow-node-header .pi {
  font-size: 12px;
}

.flow-node-number {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
}

.flow-node-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ─────────────────────────────────────────────
   Step Detail Slide-out
   ───────────────────────────────────────────── */

.step-detail {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  max-height: 55%;
  background: var(--color-bg);
  border-top: 1px solid var(--color-border);
  box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  z-index: 10;
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  overflow: hidden;
}

.step-detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border-light);
  flex-shrink: 0;
  gap: 8px;
}

.step-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  flex: 1;
  min-width: 0;
}

.step-number {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-text-primary);
}

.step-action-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  font-size: 11px;
  font-weight: 500;
  text-transform: capitalize;
  background: var(--color-bg-tertiary);
  color: var(--color-text-secondary);
}

.step-action-badge.action-api_call { background: rgba(26, 115, 232, 0.1); color: var(--color-info); }
.step-action-badge.action-data_process { background: rgba(139, 92, 246, 0.1); color: #8b5cf6; }
.step-action-badge.action-execute_code { background: rgba(245, 158, 11, 0.1); color: #f59e0b; }
.step-action-badge.action-format_output { background: rgba(52, 168, 83, 0.1); color: var(--color-success); }

.step-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  font-size: 11px;
  font-weight: 500;
}

.step-status-badge.status-completed { background: rgba(52, 168, 83, 0.1); color: var(--color-success); }
.step-status-badge.status-running { background: rgba(26, 115, 232, 0.1); color: var(--color-running); }
.step-status-badge.status-error { background: rgba(234, 67, 53, 0.1); color: var(--color-error); }
.step-status-badge.status-pending { background: var(--color-bg-tertiary); color: var(--color-text-tertiary); }
.step-status-badge.status-skipped { background: var(--color-bg-tertiary); color: var(--color-text-tertiary); }

.confirmation-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  font-size: 11px;
  font-weight: 500;
}

.confirmation-badge.confirm-pending {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}

.confirmation-badge.confirm-approved {
  background: rgba(52, 168, 83, 0.1);
  color: var(--color-success);
}

.confirmation-badge.confirm-rejected {
  background: rgba(234, 67, 53, 0.1);
  color: var(--color-error);
}

.close-step-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: none;
  color: var(--color-text-secondary);
  cursor: pointer;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.close-step-btn:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-tertiary);
}

.step-detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.step-description {
  font-size: 14px;
  color: var(--color-text-primary);
  line-height: 1.5;
  margin: 0 0 12px;
}

.step-info-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border-light);
  font-size: 13px;
}

.info-label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-text-secondary);
  font-weight: 500;
  min-width: 100px;
  flex-shrink: 0;
}

.info-label .pi {
  font-size: 12px;
}

.info-value {
  color: var(--color-text-primary);
}

.endpoint-value {
  display: flex;
  align-items: center;
  gap: 8px;
}

.method-pill {
  display: inline-block;
  padding: 1px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  text-transform: uppercase;
}

.method-pill.method-get { background: #34a853; }
.method-pill.method-post { background: #1a73e8; }
.method-pill.method-put { background: #f59e0b; color: #333; }
.method-pill.method-delete { background: #ea4335; }
.method-pill.method-patch { background: #673ab7; }

.endpoint-value code {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--color-text-primary);
}

/* ─────────────────────────────────────────────
   Step sections (reasoning, request, response)
   ───────────────────────────────────────────── */

.step-section {
  margin-top: 16px;
}

.step-section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 8px;
}

.step-section-title .pi {
  font-size: 12px;
  color: var(--color-accent);
}

.error-title .pi {
  color: var(--color-error);
}

.reasoning-box {
  padding: 12px 14px;
  background: var(--color-accent-light);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--color-text-primary);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.alternatives-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.alternatives-list li {
  padding: 8px 12px;
  border-left: 3px solid var(--color-border);
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.5;
  background: var(--color-bg-secondary);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.step-code {
  padding: 12px 14px;
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-md);
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--color-text-primary);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 240px;
  overflow-y: auto;
  margin: 0;
  line-height: 1.5;
}

.error-code {
  background: rgba(234, 67, 53, 0.06);
  color: var(--color-error);
}

.step-error-section {
  padding: 12px;
  background: rgba(234, 67, 53, 0.04);
  border-radius: var(--radius-md);
  border: 1px solid rgba(234, 67, 53, 0.15);
}

/* ─────────────────────────────────────────────
   Transitions
   ───────────────────────────────────────────── */

.step-slide-enter-active,
.step-slide-leave-active {
  transition: transform 0.25s ease, opacity 0.25s ease;
}

.step-slide-enter-from,
.step-slide-leave-to {
  transform: translateY(100%);
  opacity: 0;
}

/* ─────────────────────────────────────────────
   Responsive: Mobile stacked layout
   ───────────────────────────────────────────── */

@media (max-width: 767px) {
  .scenarios-view {
    flex-direction: column;
  }

  .scenarios-list-panel {
    width: 100%;
    min-width: 0;
    border-right: none;
    border-bottom: 1px solid var(--color-border);
  }

  .scenarios-list-panel.hidden {
    display: none;
  }

  .scenarios-detail-panel.hidden {
    display: none;
  }

  .scenarios-detail-panel {
    flex: 1;
  }

  .detail-content {
    position: relative;
  }

  .step-detail {
    max-height: 60%;
  }

  .graph-container {
    min-height: 300px;
  }

  .status-filters {
    padding: 12px 16px;
  }

  .panel-header {
    padding: 16px 16px 0;
  }

  .panel-description {
    padding: 6px 16px 0;
  }
}

/* ─────────────────────────────────────────────
   Vue Flow overrides
   ───────────────────────────────────────────── */

.graph-container :deep(.vue-flow__controls) {
  box-shadow: var(--shadow-sm);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  overflow: hidden;
}

.graph-container :deep(.vue-flow__controls-button) {
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border-light);
  color: var(--color-text-secondary);
  width: 28px;
  height: 28px;
}

.graph-container :deep(.vue-flow__controls-button:hover) {
  background: var(--color-accent-light);
  color: var(--color-accent);
}

.graph-container :deep(.vue-flow__minimap) {
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
}

.graph-container :deep(.vue-flow__background) {
  background: var(--color-bg);
}
</style>
