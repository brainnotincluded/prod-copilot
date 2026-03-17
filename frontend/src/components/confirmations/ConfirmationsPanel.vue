<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAuth } from '@/composables/useAuth'
import { useLocale } from '@/composables/useLocale'

interface Confirmation {
  id: string
  correlation_id: string
  action: string
  endpoint_method: string
  endpoint_path: string
  payload_summary: string
  status: string
  created_at: string
}

interface ResolveResult {
  resolved: string
  flash: 'approved' | 'rejected'
  timer: ReturnType<typeof setTimeout> | null
}

const { getAuthHeaders, canApprove, user } = useAuth()
const { t } = useLocale()

const isOpen = ref(false)
const confirmations = ref<Confirmation[]>([])
const resolving = ref<Set<string>>(new Set())
const resolveResults = ref<Map<string, ResolveResult>>(new Map())
const pollTimer = ref<ReturnType<typeof setInterval> | null>(null)

const pendingCount = computed(() => confirmations.value.length)

const methodColor = (method: string): string => {
  switch (method.toUpperCase()) {
    case 'GET': return 'var(--color-success)'
    case 'POST': return 'var(--color-accent)'
    case 'PUT': return 'var(--color-warning)'
    case 'PATCH': return 'var(--color-warning)'
    case 'DELETE': return 'var(--color-error)'
    default: return 'var(--color-text-secondary)'
  }
}

function formatTime(dateStr: string): string {
  try {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return 'just now'
    if (diffMin < 60) return `${diffMin}m ago`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr}h ago`
    const diffDay = Math.floor(diffHr / 24)
    return `${diffDay}d ago`
  } catch {
    return dateStr
  }
}

async function fetchConfirmations() {
  try {
    const response = await fetch('/api/v1/confirmations?status=pending', {
      headers: getAuthHeaders(),
    })
    if (response.ok) {
      confirmations.value = await response.json()
    }
  } catch {
    // Silently fail — will retry on next poll
  }
}

async function resolve(id: string, status: 'approved' | 'rejected') {
  if (resolving.value.has(id)) return
  resolving.value.add(id)

  try {
    const response = await fetch(`/api/v1/confirmations/${id}/resolve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({
        status,
        resolver: user.value?.email || 'unknown',
      }),
    })

    if (response.ok) {
      // Show flash result then remove
      const result: ResolveResult = { resolved: status, flash: status, timer: null }
      resolveResults.value.set(id, result)

      result.timer = setTimeout(() => {
        confirmations.value = confirmations.value.filter(c => c.id !== id)
        resolveResults.value.delete(id)
      }, 1200)
    }
  } catch {
    // Show error briefly
    const result: ResolveResult = { resolved: 'error', flash: status, timer: null }
    resolveResults.value.set(id, result)
    result.timer = setTimeout(() => {
      resolveResults.value.delete(id)
    }, 2000)
  } finally {
    resolving.value.delete(id)
  }
}

function togglePanel() {
  isOpen.value = !isOpen.value
}

function closePanel() {
  isOpen.value = false
}

function handleClickOutside(e: MouseEvent) {
  const panel = document.querySelector('.confirmations-wrapper')
  if (panel && !panel.contains(e.target as Node)) {
    closePanel()
  }
}

onMounted(() => {
  fetchConfirmations()
  pollTimer.value = setInterval(fetchConfirmations, 10000)
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
  document.removeEventListener('click', handleClickOutside)
  // Clean up any pending timers
  for (const result of resolveResults.value.values()) {
    if (result.timer) clearTimeout(result.timer)
  }
})
</script>

<template>
  <div class="confirmations-wrapper">
    <!-- Bell Button -->
    <button
      class="bell-btn"
      :title="t('confirmations.title')"
      @click.stop="togglePanel"
    >
      <i class="pi pi-bell"></i>
      <span v-if="pendingCount > 0" class="badge">{{ pendingCount }}</span>
    </button>

    <!-- Dropdown Panel -->
    <Transition name="panel">
      <div v-if="isOpen" class="confirmations-panel" @click.stop>
        <div class="panel-header">
          <span class="panel-title">{{ t('confirmations.title') }}</span>
          <button class="close-btn" @click="closePanel">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <div class="panel-body">
          <!-- Empty State -->
          <div v-if="confirmations.length === 0" class="empty-state">
            <i class="pi pi-check-circle empty-icon"></i>
            <span>{{ t('confirmations.empty') }}</span>
          </div>

          <!-- Confirmation Items -->
          <TransitionGroup name="item" tag="div" class="items-list">
            <div
              v-for="item in confirmations"
              :key="item.id"
              class="confirmation-item"
              :class="{
                'item-approved': resolveResults.get(item.id)?.resolved === 'approved',
                'item-rejected': resolveResults.get(item.id)?.resolved === 'rejected',
                'item-error': resolveResults.get(item.id)?.resolved === 'error',
              }"
            >
              <!-- Action Name -->
              <div class="item-action">
                <span class="action-name">{{ item.action }}</span>
                <span class="item-time">
                  <i class="pi pi-clock"></i>
                  {{ formatTime(item.created_at) }}
                </span>
              </div>

              <!-- Endpoint -->
              <div class="item-endpoint">
                <span class="method-badge" :style="{ color: methodColor(item.endpoint_method) }">
                  {{ item.endpoint_method.toUpperCase() }}
                </span>
                <span class="endpoint-path">{{ item.endpoint_path }}</span>
              </div>

              <!-- Payload Summary -->
              <div v-if="item.payload_summary" class="item-payload">
                {{ item.payload_summary }}
              </div>

              <!-- Resolve Result Flash -->
              <div v-if="resolveResults.has(item.id)" class="resolve-flash">
                <template v-if="resolveResults.get(item.id)?.resolved === 'approved'">
                  <i class="pi pi-check"></i> {{ t('confirmations.approved') }}
                </template>
                <template v-else-if="resolveResults.get(item.id)?.resolved === 'rejected'">
                  <i class="pi pi-times"></i> {{ t('confirmations.rejected') }}
                </template>
                <template v-else>
                  <i class="pi pi-exclamation-triangle"></i> {{ t('confirmations.resolve_error') }}
                </template>
              </div>

              <!-- Action Buttons -->
              <div v-else class="item-actions">
                <template v-if="canApprove">
                  <button
                    class="action-btn approve-btn"
                    :disabled="resolving.has(item.id)"
                    @click="resolve(item.id, 'approved')"
                  >
                    <i class="pi pi-check"></i>
                    {{ t('confirmations.approve') }}
                  </button>
                  <button
                    class="action-btn reject-btn"
                    :disabled="resolving.has(item.id)"
                    @click="resolve(item.id, 'rejected')"
                  >
                    <i class="pi pi-times"></i>
                    {{ t('confirmations.reject') }}
                  </button>
                </template>
                <template v-else>
                  <span class="awaiting-label">
                    <i class="pi pi-clock"></i>
                    {{ t('confirmations.awaiting') }}
                  </span>
                </template>
              </div>
            </div>
          </TransitionGroup>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.confirmations-wrapper {
  position: relative;
}

/* Bell Button */
.bell-btn {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  background: none;
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  transition: background var(--transition-fast), color var(--transition-fast);
  cursor: pointer;
}

.bell-btn:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-primary);
}

.bell-btn .pi-bell {
  font-size: 18px;
}

.badge {
  position: absolute;
  top: 2px;
  right: 2px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: var(--radius-full);
  background: var(--color-error);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  line-height: 18px;
  text-align: center;
  pointer-events: none;
}

/* Panel */
.confirmations-panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 380px;
  max-height: 480px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border-light);
  flex-shrink: 0;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: none;
  border-radius: var(--radius-sm);
  color: var(--color-text-tertiary);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.close-btn:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-primary);
}

/* Panel Body */
.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 32px 16px;
  color: var(--color-text-tertiary);
  font-size: 13px;
}

.empty-icon {
  font-size: 28px;
  color: var(--color-success);
  opacity: 0.6;
}

/* Items */
.items-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.confirmation-item {
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-light);
  transition: background var(--transition-fast), border-color var(--transition-fast), opacity var(--transition-normal);
}

.confirmation-item:hover {
  border-color: var(--color-border);
}

.confirmation-item.item-approved {
  background: rgba(52, 168, 83, 0.08);
  border-color: var(--color-success);
}

.confirmation-item.item-rejected {
  background: rgba(234, 67, 53, 0.08);
  border-color: var(--color-error);
}

.confirmation-item.item-error {
  background: rgba(234, 67, 53, 0.05);
}

/* Item Layout */
.item-action {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.action-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.item-time {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.item-time .pi-clock {
  font-size: 10px;
}

.item-endpoint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-family: var(--font-mono);
  font-size: 12px;
}

.method-badge {
  font-weight: 700;
  font-size: 11px;
  letter-spacing: 0.3px;
}

.endpoint-path {
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-payload {
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-bottom: 8px;
  padding: 4px 8px;
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-sm);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Resolve Flash */
.resolve-flash {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 0 2px;
}

.item-approved .resolve-flash {
  color: var(--color-success);
}

.item-rejected .resolve-flash {
  color: var(--color-error);
}

.item-error .resolve-flash {
  color: var(--color-error);
}

/* Action Buttons */
.item-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 6px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border: none;
  border-radius: var(--radius-md);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition-fast), opacity var(--transition-fast);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-btn .pi {
  font-size: 11px;
}

.approve-btn {
  background: var(--color-success);
  color: #fff;
}

.approve-btn:hover:not(:disabled) {
  opacity: 0.85;
}

.reject-btn {
  background: var(--color-bg-tertiary);
  color: var(--color-error);
  border: 1px solid var(--color-border);
}

.reject-btn:hover:not(:disabled) {
  background: rgba(234, 67, 53, 0.08);
  border-color: var(--color-error);
}

.awaiting-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-tertiary);
  font-style: italic;
}

.awaiting-label .pi-clock {
  font-size: 11px;
}

/* Panel open/close animation */
.panel-enter-active {
  transition: opacity var(--transition-fast), transform var(--transition-fast);
}

.panel-leave-active {
  transition: opacity var(--transition-fast), transform var(--transition-fast);
}

.panel-enter-from {
  opacity: 0;
  transform: translateY(-8px) scale(0.96);
}

.panel-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.96);
}

/* Item list animation */
.item-enter-active {
  transition: opacity var(--transition-normal), transform var(--transition-normal);
}

.item-leave-active {
  transition: opacity var(--transition-fast), transform var(--transition-fast);
}

.item-enter-from {
  opacity: 0;
  transform: translateX(12px);
}

.item-leave-to {
  opacity: 0;
  transform: translateX(-12px);
}

/* Mobile: full-width panel */
@media (max-width: 768px) {
  .confirmations-panel {
    position: fixed;
    top: var(--mobile-header-height);
    left: 8px;
    right: 8px;
    width: auto;
    max-height: calc(100vh - var(--mobile-header-height) - var(--mobile-nav-height) - 24px);
  }
}

@media (max-width: 480px) {
  .confirmations-panel {
    left: 4px;
    right: 4px;
    border-radius: var(--radius-md);
  }

  .item-actions {
    flex-direction: column;
    gap: 6px;
  }

  .action-btn {
    width: 100%;
    justify-content: center;
    padding: 8px 12px;
  }
}
</style>
