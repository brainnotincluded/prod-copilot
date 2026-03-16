/**
 * Setup file for enabling mock mode
 * 
 * This file patches the stores to use mock data when
 * VITE_USE_MOCKS=true or when ?useMocks query param is present
 */

import { useEndpointsStore } from '@/stores/endpoints'
import { useSwaggerStore } from '@/stores/swagger'
import { mockEndpoints, mockSwaggerSources } from './api-maps.mock'

let isMockEnabled = false

export function enableMocks() {
  if (isMockEnabled) return
  isMockEnabled = true
  
  console.log('[MockSetup] Enabling mock mode for stores')
  
  // Patch the endpoints store
  const originalEndpointsStore = useEndpointsStore
  
  // Override store initialization to use mock data
  const endpointsStore = useEndpointsStore()
  endpointsStore.$patch({
    endpoints: mockEndpoints as any,
    isLoading: false,
    error: null,
    stats: {
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
    },
  })
  
  // Override fetch methods
  endpointsStore.fetchEndpoints = async () => { /* no-op */ }
  endpointsStore.fetchStats = async () => { /* no-op */ }
  
  // Patch swagger store
  const swaggerStore = useSwaggerStore()
  swaggerStore.$patch({
    swaggers: mockSwaggerSources as any,
    isLoading: false,
    error: null,
  })
  swaggerStore.fetchSwaggers = async () => { /* no-op */ }
}

export function isMockModeEnabled(): boolean {
  return isMockEnabled || 
    import.meta.env.VITE_USE_MOCKS === 'true' ||
    new URLSearchParams(window.location.search).has('useMocks')
}

// Auto-enable if query param present
if (isMockModeEnabled()) {
  // Wait for stores to be initialized
  setTimeout(enableMocks, 0)
}
