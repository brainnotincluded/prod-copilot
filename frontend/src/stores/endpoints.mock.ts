/**
 * Mock version of endpoints store for testing
 * Usage: Replace import in tests:
 * import { useEndpointsStore } from '@/stores/endpoints.mock'
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { mockEndpoints, mockSwaggerSources } from '@/mocks/api-maps.mock'
import type { EndpointItem, EndpointStats } from '@/types'

export const useEndpointsStore = defineStore('endpoints', () => {
  const endpoints = ref<EndpointItem[]>(mockEndpoints as EndpointItem[])
  const stats = ref<EndpointStats | null>({
    total: mockEndpoints.length,
    by_method: {
      GET: mockEndpoints.filter(e => e.method === 'GET').length,
      POST: mockEndpoints.filter(e => e.method === 'POST').length,
      PUT: mockEndpoints.filter(e => e.method === 'PUT').length,
      DELETE: mockEndpoints.filter(e => e.method === 'DELETE').length,
      PATCH: 0,
    },
    by_source: {
      'JSONPlaceholder API': mockEndpoints.filter(e => e.swagger_source_id === 1).length,
      'Pet Store API': mockEndpoints.filter(e => e.swagger_source_id === 2).length,
    },
  })
  const methods = ref<string[]>(['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const filters = ref({
    method: '',
    search: '',
    sourceId: null as number | null,
  })

  // Mock fetch functions - data already loaded
  async function fetchEndpoints() {
    // Data already loaded from mocks
    isLoading.value = false
  }

  async function fetchStats() {
    // Stats already loaded
  }

  async function fetchMethods() {
    // Methods already loaded
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
