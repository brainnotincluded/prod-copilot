<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useLocale } from '@/composables/useLocale'
import type { SwaggerSource } from '@/types'

const props = defineProps<{
  swaggers: SwaggerSource[]
  loading: boolean
}>()

const emit = defineEmits<{
  delete: [id: number]
  refresh: []
}>()

const router = useRouter()
const { api } = useApi()
const { showToast } = useToast()
const { t } = useLocale()

const sourceStats = ref<Record<number, { total_endpoints: number; by_method: Record<string, number>; base_url?: string }>>({})
const refreshing = ref(false)
const touchStartY = ref(0)
const touchEndY = ref(0)
const isPulling = ref(false)
const pullProgress = ref(0)
const swipedItemId = ref<number | null>(null)
const touchStartX = ref(0)

const methodColors: Record<string, string> = {
  GET: '#34a853',
  POST: '#1a73e8',
  PUT: '#fbbc04',
  DELETE: '#ea4335',
  PATCH: '#673ab7',
}

onMounted(() => {
  fetchAllStats()
})

async function fetchAllStats() {
  for (const swagger of props.swaggers) {
    try {
      const response = await api.get(`/swagger/${swagger.id}/stats`)
      sourceStats.value[swagger.id] = response.data
    } catch {
      // Silently skip failed stats
    }
  }
}

watch(() => props.swaggers, () => {
  fetchAllStats()
}, { deep: true })

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) {
    return t('swagger.today')
  } else if (diffDays === 1) {
    return t('swagger.yesterday')
  } else if (diffDays < 7) {
    return t('swagger.daysAgo', diffDays)
  }

  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function confirmDelete(id: number, name: string) {
  if (window.confirm(t('swagger.confirmDelete', name))) {
    emit('delete', id)
    showToast(t('swagger.deleted', name), 'success')
  }
}

function viewEndpoints(sourceId: number) {
  router.push({ path: '/endpoints', query: { source: sourceId.toString() } })
}

function getStats(id: number) {
  return sourceStats.value[id] || null
}

function getEndpointCount(swagger: SwaggerSource): number {
  return getStats(swagger.id)?.total_endpoints ?? swagger.endpoint_count
}

function getBaseUrl(swagger: SwaggerSource): string | undefined {
  return getStats(swagger.id)?.base_url || (swagger as any).base_url
}

function isValidUrl(str: string): boolean {
  try {
    new URL(str)
    return true
  } catch {
    return false
  }
}

// Pull to refresh handlers
function handleTouchStart(event: TouchEvent) {
  touchStartY.value = event.touches[0].clientY
  touchStartX.value = event.touches[0].clientX
}

function handleTouchMove(event: TouchEvent) {
  // Check if it's a horizontal swipe for delete
  const touchX = event.touches[0].clientX
  const diffX = touchStartX.value - touchX
  
  // If horizontal swipe detected, don't handle pull to refresh
  if (Math.abs(diffX) > 20) {
    return
  }
  
  // Pull to refresh logic
  if (window.scrollY === 0 && !refreshing.value) {
    touchEndY.value = event.touches[0].clientY
    const diff = touchEndY.value - touchStartY.value
    if (diff > 0) {
      isPulling.value = true
      pullProgress.value = Math.min(diff / 80, 1)
      event.preventDefault()
    }
  }
}

function handleTouchEnd() {
  if (isPulling.value && pullProgress.value >= 1) {
    triggerRefresh()
  }
  isPulling.value = false
  pullProgress.value = 0
}

async function triggerRefresh() {
  if (refreshing.value) return
  refreshing.value = true
  await fetchAllStats()
  emit('refresh')
  setTimeout(() => {
    refreshing.value = false
  }, 500)
}

// Swipe to delete handlers
function handleCardTouchStart(event: TouchEvent, id: number) {
  touchStartX.value = event.touches[0].clientX
}

function handleCardTouchMove(event: TouchEvent, id: number) {
  const touchX = event.touches[0].clientX
  const diff = touchStartX.value - touchX
  
  if (diff > 50) {
    swipedItemId.value = id
  } else if (diff < -30) {
    swipedItemId.value = null
  }
}

function handleCardTouchEnd(id: number, name: string) {
  if (swipedItemId.value === id) {
    // Keep it swiped, wait for delete action
  }
}
</script>

<template>
  <div 
    class="swagger-list"
    @touchstart="handleTouchStart"
    @touchmove="handleTouchMove"
    @touchend="handleTouchEnd"
  >
    <!-- Pull to refresh indicator -->
    <div 
      class="pull-indicator"
      :class="{ 'is-pulling': isPulling, 'is-refreshing': refreshing }"
      :style="{ transform: `translateY(${(isPulling ? Math.min(pullProgress * 60, 60) : 0) - 60}px)` }"
    >
      <i class="pi" :class="refreshing ? 'pi-spin pi-spinner' : 'pi-refresh'"></i>
      <span>{{ refreshing ? t('swagger.refreshing') : t('swagger.pullToRefresh') }}</span>
    </div>

    <div v-if="loading && swaggers.length === 0" class="list-loading">
      <i class="pi pi-spin pi-spinner"></i>
      <span>{{ t('swagger.loading') }}</span>
    </div>

    <div v-else-if="swaggers.length === 0" class="list-empty">
      <i class="pi pi-inbox list-empty-icon"></i>
      <p>{{ t('swagger.noSources') }}</p>
      <p class="list-empty-hint">{{ t('swagger.noSourcesHint') }}</p>
    </div>

    <div v-else class="list-items">
      <div
        v-for="swagger in swaggers"
        :key="swagger.id"
        class="list-card-wrapper"
        :class="{ 'is-swiped': swipedItemId === swagger.id }"
        @touchstart="handleCardTouchStart($event, swagger.id)"
        @touchmove="handleCardTouchMove($event, swagger.id)"
        @touchend="handleCardTouchEnd(swagger.id, swagger.name)"
      >
        <!-- Swipe delete action -->
        <div class="swipe-actions">
          <button
            class="swipe-delete-btn"
            @click="confirmDelete(swagger.id, swagger.name)"
          >
            <i class="pi pi-trash"></i>
            <span>{{ t('common.delete') }}</span>
          </button>
        </div>

        <div class="list-card">
          <div class="card-top">
            <div class="card-status">
              <span
                class="status-dot"
                :class="getBaseUrl(swagger) ? 'green' : 'yellow'"
                :title="getBaseUrl(swagger) ? t('swagger.baseUrlDetected') : t('swagger.noBaseUrl')"
              ></span>
            </div>
            <div class="card-info">
              <div class="card-name">{{ swagger.name }}</div>
              <div v-if="getBaseUrl(swagger)" class="card-base-url mobile-hidden">
                <a
                  v-if="isValidUrl(getBaseUrl(swagger)!)"
                  :href="getBaseUrl(swagger)"
                  target="_blank"
                  rel="noopener"
                  class="base-url-link"
                >{{ getBaseUrl(swagger) }}</a>
                <span v-else class="base-url-text">{{ getBaseUrl(swagger) }}</span>
              </div>
              <div class="card-meta">
                <span class="endpoint-badge">
                  {{ getEndpointCount(swagger) }} {{ t('common.endpoints') }}
                </span>
                <span class="meta-dot mobile-hidden"></span>
                <span class="import-date mobile-hidden">
                  <i class="pi pi-calendar meta-icon"></i>
                  {{ formatDate(swagger.created_at) }}
                </span>
                <template v-if="swagger.url">
                  <span class="meta-dot mobile-hidden"></span>
                  <a :href="swagger.url" target="_blank" rel="noopener" class="source-url mobile-hidden">
                    <i class="pi pi-external-link meta-icon"></i>
                    {{ t('swagger.source') }}
                  </a>
                </template>
              </div>
            </div>
            <div class="card-actions">
              <button
                class="action-btn view-btn"
                @click="viewEndpoints(swagger.id)"
                :title="t('swagger.viewInMaps')"
              >
                <i class="pi pi-map"></i>
              </button>
              <button
                class="action-btn delete-btn"
                @click="confirmDelete(swagger.id, swagger.name)"
                :title="t('swagger.deleteSource')"
              >
                <i class="pi pi-trash"></i>
              </button>
            </div>
          </div>

          <!-- Method breakdown -->
          <div v-if="getStats(swagger.id)?.by_method" class="method-breakdown">
            <span
              v-for="(count, method) in getStats(swagger.id)!.by_method"
              :key="method"
              class="method-pill"
              :style="{
                background: (methodColors[method as string] || '#9e9e9e') + '18',
                color: methodColors[method as string] || '#9e9e9e',
                borderColor: (methodColors[method as string] || '#9e9e9e') + '40',
              }"
            >
              {{ method }} {{ count }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.swagger-list {
  margin-top: 4px;
  position: relative;
}

/* Pull to refresh indicator */
.pull-indicator {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px;
  color: var(--color-text-tertiary);
  font-size: 13px;
  transition: transform 0.2s ease, opacity 0.2s ease;
  z-index: 1;
  pointer-events: none;
  opacity: 0;
}

.pull-indicator.is-pulling,
.pull-indicator.is-refreshing {
  opacity: 1;
}

.pull-indicator i {
  font-size: 16px;
}

.pull-indicator.is-refreshing {
  position: relative;
  transform: translateY(0) !important;
}

.list-loading,
.list-empty {
  padding: 40px 32px;
  text-align: center;
  color: var(--color-text-tertiary);
  font-size: 14px;
}

.list-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.list-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.list-empty-icon {
  font-size: 32px;
  color: var(--color-border);
  margin-bottom: 8px;
}

.list-empty-hint {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

.list-items {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.list-card-wrapper {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-lg);
}

.swipe-actions {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-right: 16px;
  background: var(--color-error);
  opacity: 0;
  transition: opacity 0.2s ease;
}

.list-card-wrapper.is-swiped .swipe-actions {
  opacity: 1;
}

.swipe-delete-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  background: none;
  border: none;
  color: white;
  font-size: 12px;
  cursor: pointer;
  min-height: 60px;
  min-width: 60px;
  touch-action: manipulation;
}

.swipe-delete-btn i {
  font-size: 20px;
}

.list-card {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: 16px;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast), transform 0.2s ease;
  background: var(--color-bg);
  position: relative;
  z-index: 2;
}

.list-card-wrapper.is-swiped .list-card {
  transform: translateX(-80px);
}

.list-card:hover {
  border-color: var(--color-border);
  box-shadow: var(--shadow-sm);
}

.card-top {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.card-status {
  flex-shrink: 0;
  margin-top: 5px;
}

.status-dot {
  display: block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.green {
  background: var(--color-success);
  box-shadow: 0 0 0 3px rgba(52, 168, 83, 0.15);
}

.status-dot.yellow {
  background: var(--color-warning);
  box-shadow: 0 0 0 3px rgba(251, 188, 4, 0.15);
}

.card-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-base-url {
  font-family: var(--font-mono);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.base-url-link {
  color: var(--color-text-tertiary);
  text-decoration: none;
}

.base-url-link:hover {
  color: var(--color-accent);
  text-decoration: underline;
}

.base-url-text {
  color: var(--color-text-tertiary);
}

.card-meta {
  font-size: 12px;
  color: var(--color-text-tertiary);
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 2px;
}

.meta-icon {
  font-size: 11px;
  margin-right: 2px;
}

.endpoint-badge {
  font-weight: 600;
  color: var(--color-accent);
  background: var(--color-accent-light);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
}

.meta-dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--color-border);
  flex-shrink: 0;
}

.import-date {
  display: flex;
  align-items: center;
}

.source-url {
  display: flex;
  align-items: center;
  color: var(--color-accent);
  font-size: 12px;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.action-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: none;
  border-radius: var(--radius-md);
  color: var(--color-text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.view-btn:hover {
  background: var(--color-accent-light);
  color: var(--color-accent);
}

.delete-btn:hover {
  background: #fde7e7;
  color: var(--color-error);
}

.method-breakdown {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--color-border-light);
}

.method-pill {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 10px;
  border: 1px solid;
  letter-spacing: 0.3px;
}

/* Tablet (< 768px) */
@media (max-width: 768px) {
  .list-items {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .list-card {
    padding: 14px;
  }

  .card-name {
    font-size: 14px;
  }

  .action-btn {
    width: 40px;
    height: 40px;
    font-size: 15px;
  }

  .endpoint-badge {
    font-size: 12px;
    padding: 3px 10px;
  }

  .method-pill {
    font-size: 11px;
    padding: 3px 8px;
  }
}

/* Tablet (641px - 1024px) - 2 колонки */
@media (min-width: 641px) and (max-width: 1024px) {
  .list-items {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .list-card {
    padding: 14px;
    height: 100%;
  }

  .card-top {
    flex-direction: column;
    gap: 10px;
  }

  .card-status {
    margin-top: 0;
  }

  .card-actions {
    align-self: flex-end;
    margin-top: auto;
  }

  .method-breakdown {
    margin-top: 12px;
  }
}

/* Mobile (max-width: 640px) */
@media (max-width: 640px) {
  .swagger-list {
    margin-top: 0;
  }

  /* Hide pull-to-refresh text when not active */
  .pull-indicator:not(.is-pulling):not(.is-refreshing) {
    display: none;
  }

  .pull-indicator {
    position: relative;
    padding: 8px;
    font-size: 12px;
    transform: none !important;
  }

  .pull-indicator.is-refreshing {
    margin-bottom: 8px;
  }

  .list-card-wrapper {
    border-radius: var(--radius-md);
  }

  .list-card {
    padding: 14px 12px;
    border-radius: var(--radius-md);
  }

  .list-card-wrapper.is-swiped .list-card {
    transform: translateX(-90px);
  }

  .card-top {
    gap: 10px;
  }

  .card-name {
    font-size: 14px;
    font-weight: 600;
  }

  /* Увеличенные кнопки действий - min 44px touch target */
  .card-actions {
    gap: 8px;
  }

  .action-btn {
    width: 44px;
    height: 44px;
    font-size: 17px;
    min-height: 44px;
    min-width: 44px;
    touch-action: manipulation;
  }

  .action-btn:active {
    transform: scale(0.95);
  }

  .mobile-hidden {
    display: none !important;
  }

  .card-meta {
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
    margin-top: 8px;
  }

  .endpoint-badge {
    font-size: 12px;
    padding: 4px 10px;
  }

  .method-breakdown {
    margin-top: 12px;
    padding-top: 12px;
    gap: 6px;
  }

  .method-pill {
    font-size: 11px;
    padding: 3px 8px;
  }

  .pull-indicator {
    font-size: 12px;
    padding: 12px;
  }

  .list-loading,
  .list-empty {
    padding: 32px 20px;
  }

  /* Увеличенная swipe delete кнопка */
  .swipe-actions {
    padding-right: 12px;
  }

  .swipe-delete-btn {
    min-height: 72px;
    min-width: 72px;
    font-size: 13px;
    gap: 6px;
  }

  .swipe-delete-btn i {
    font-size: 24px;
  }
}

/* Small mobile (max-width: 375px) */
@media (max-width: 375px) {
  .list-card {
    padding: 12px 10px;
  }

  .card-name {
    font-size: 13px;
  }

  .action-btn {
    width: 44px;
    height: 44px;
    font-size: 16px;
  }

  .endpoint-badge {
    font-size: 11px;
    padding: 3px 8px;
  }
}

@media (min-width: 641px) {
  .swipe-actions {
    display: none;
  }
}
</style>
