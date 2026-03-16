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
      const response = await api.get(`/api/swagger/${swagger.id}/stats`)
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
</script>

<template>
  <div class="swagger-list">
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
        class="list-card"
      >
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
            <div v-if="getBaseUrl(swagger)" class="card-base-url">
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
              <span class="meta-dot"></span>
              <span class="import-date">
                <i class="pi pi-calendar meta-icon"></i>
                {{ formatDate(swagger.created_at) }}
              </span>
              <template v-if="swagger.url">
                <span class="meta-dot"></span>
                <a :href="swagger.url" target="_blank" rel="noopener" class="source-url">
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
</template>

<style scoped>
.swagger-list {
  margin-top: 4px;
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

.list-card {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: 16px;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  background: var(--color-bg);
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
  width: 32px;
  height: 32px;
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

/* Responsive */
@media (max-width: 640px) {
  .list-card {
    padding: 12px;
  }

  .card-meta {
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
  }

  .meta-dot {
    display: none;
  }
}
</style>
