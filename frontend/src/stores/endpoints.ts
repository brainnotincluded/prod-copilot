import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useApi } from '@/composables/useApi'
import type { EndpointItem, EndpointStats } from '@/types'

export const useEndpointsStore = defineStore('endpoints', () => {
  const endpoints = ref<EndpointItem[]>([])
  const stats = ref<EndpointStats | null>(null)
  const methods = ref<string[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const filters = ref({
    method: '',
    search: '',
    sourceId: null as number | null,
  })

  const { api } = useApi()

  async function fetchEndpoints() {
    isLoading.value = true
    error.value = null
    try {
      const params: Record<string, any> = {}
      if (filters.value.sourceId) {
        params.swagger_source_id = filters.value.sourceId
      }
      if (filters.value.method) {
        params.method = filters.value.method
      }
      const response = await api.get<EndpointItem[]>('/api/endpoints/list', { params })
      endpoints.value = response.data
    } catch (err: any) {
      error.value = err.message || 'Failed to fetch endpoints'
    } finally {
      isLoading.value = false
    }
  }

  async function fetchStats() {
    try {
      const response = await api.get<EndpointStats>('/api/endpoints/stats')
      stats.value = response.data
    } catch (err: any) {
      // Stats are optional, don't block on failure
      console.error('Failed to fetch endpoint stats:', err)
    }
  }

  async function fetchMethods() {
    try {
      const response = await api.get<string[]>('/api/endpoints/methods')
      methods.value = response.data
    } catch (err: any) {
      console.error('Failed to fetch methods:', err)
    }
  }

  const filteredEndpoints = computed(() => {
    return endpoints.value.filter((ep) => {
      if (filters.value.method && ep.method !== filters.value.method) return false
      if (filters.value.search) {
        const q = filters.value.search.toLowerCase()
        const matchPath = ep.path.toLowerCase().includes(q)
        const matchSummary = (ep.summary || '').toLowerCase().includes(q)
        const matchDescription = (ep.description || '').toLowerCase().includes(q)
        if (!matchPath && !matchSummary && !matchDescription) return false
      }
      return true
    })
  })

  function setFilter(key: 'method' | 'search' | 'sourceId', value: string | number | null) {
    if (key === 'method') {
      filters.value.method = value as string
    } else if (key === 'search') {
      filters.value.search = value as string
    } else if (key === 'sourceId') {
      filters.value.sourceId = value as number | null
    }
  }

  function clearFilters() {
    filters.value.method = ''
    filters.value.search = ''
    filters.value.sourceId = null
  }

  return {
    endpoints,
    stats,
    methods,
    isLoading,
    error,
    filters,
    filteredEndpoints,
    fetchEndpoints,
    fetchStats,
    fetchMethods,
    setFilter,
    clearFilters,
  }
})
