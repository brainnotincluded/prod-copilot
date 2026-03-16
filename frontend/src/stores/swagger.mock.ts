/**
 * Mock version of swagger store for testing
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { mockSwaggerSources } from '@/mocks/api-maps.mock'
import type { SwaggerSource } from '@/types'

export const useSwaggerStore = defineStore('swagger', () => {
  const swaggers = ref<SwaggerSource[]>(mockSwaggerSources as SwaggerSource[])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Mock fetch - data already loaded
  async function fetchSwaggers() {
    // Data already loaded from mocks
  }

  async function deleteSwagger(id: number) {
    const index = swaggers.value.findIndex(s => s.id === id)
    if (index !== -1) {
      swaggers.value.splice(index, 1)
    }
  }

  // Mock upload functions
  async function uploadSwagger(file: File) {
    console.log('[Mock] Uploading swagger file:', file.name)
    return { id: 3, name: file.name, endpoints_count: 10 }
  }

  async function uploadSwaggerFromUrl(url: string, name?: string) {
    console.log('[Mock] Importing swagger from URL:', url)
    return { id: 4, name: name || 'Imported API', endpoints_count: 15 }
  }

  return {
    swaggers,
    isLoading,
    error,
    fetchSwaggers,
    deleteSwagger,
    uploadSwagger,
    uploadSwaggerFromUrl,
  }
})
