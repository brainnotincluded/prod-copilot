/**
 * Mock API composable for testing
 * 
 * Usage:
 * import { useMockApi } from '@/composables/useMockApi'
 * 
 * // Enable mocks
 * useMockApi().enable()
 * 
 * // Disable mocks
 * useMockApi().disable()
 */

import { ref } from 'vue'
import { mockEndpoints, mockSwaggerSources } from '@/mocks/api-maps.mock'

const isEnabled = ref(false)

export function useMockApi() {
  function enable() {
    isEnabled.value = true
    
    // Override fetch for testing
    const originalFetch = window.fetch
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString()
      
      if (url.includes('/endpoints/list')) {
        return new Response(JSON.stringify(mockEndpoints), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      
      if (url.includes('/swagger/list')) {
        return new Response(JSON.stringify(mockSwaggerSources), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      
      if (url.includes('/endpoints/stats')) {
        return new Response(
          JSON.stringify({
            total: mockEndpoints.length,
            by_method: {
              GET: mockEndpoints.filter(e => e.method === 'GET').length,
              POST: mockEndpoints.filter(e => e.method === 'POST').length,
              PUT: mockEndpoints.filter(e => e.method === 'PUT').length,
              DELETE: mockEndpoints.filter(e => e.method === 'DELETE').length,
              PATCH: mockEndpoints.filter(e => e.method === 'PATCH').length,
            },
            by_source: mockSwaggerSources.reduce((acc, source) => {
              acc[source.name] = mockEndpoints.filter(e => e.swagger_source_id === source.id).length
              return acc
            }, {} as Record<string, number>),
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        )
      }
      
      // Fall through to original fetch
      return originalFetch(input, init)
    }
    
    // Store original for restoration
    ;(window as any).__originalFetch = originalFetch
  }
  
  function disable() {
    isEnabled.value = false
    if ((window as any).__originalFetch) {
      window.fetch = (window as any).__originalFetch
    }
  }
  
  return {
    isEnabled,
    enable,
    disable,
  }
}

// Auto-enable mocks in test mode or when VITE_USE_MOCKS env var is set
export function autoEnableMocks() {
  const useMocks = import.meta.env.VITE_USE_MOCKS === 'true' || 
                   import.meta.env.MODE === 'test' ||
                   new URLSearchParams(window.location.search).has('useMocks')
  
  if (useMocks) {
    useMockApi().enable()
    console.log('[MockAPI] Mocks enabled for testing')
  }
}
