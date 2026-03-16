import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'
import type { SwaggerSource, SwaggerUploadResult } from '@/types'

export const useSwaggerStore = defineStore('swagger', () => {
  const swaggers = ref<SwaggerSource[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const { api } = useApi()

  async function fetchSwaggers() {
    isLoading.value = true
    error.value = null
    try {
      const response = await api.get<SwaggerSource[]>('/api/swagger/list')
      swaggers.value = response.data
    } catch (err: any) {
      error.value = err.message || 'Failed to fetch swagger sources'
    } finally {
      isLoading.value = false
    }
  }

  async function uploadSwagger(file: File): Promise<SwaggerUploadResult> {
    isLoading.value = true
    error.value = null
    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await api.post<SwaggerUploadResult>('/api/swagger/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      await fetchSwaggers()
      return response.data
    } catch (err: any) {
      error.value = err.message || 'Failed to upload swagger file'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function uploadSwaggerFromUrl(url: string, name?: string): Promise<SwaggerUploadResult> {
    isLoading.value = true
    error.value = null
    try {
      const formData = new FormData()
      formData.append('url', url)
      if (name) {
        formData.append('name', name)
      }
      const response = await api.post<SwaggerUploadResult>('/api/swagger/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      await fetchSwaggers()
      return response.data
    } catch (err: any) {
      error.value = err.message || 'Failed to import swagger from URL'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function deleteSwagger(id: number) {
    try {
      await api.delete(`/api/swagger/${id}`)
      swaggers.value = swaggers.value.filter((s) => s.id !== id)
    } catch (err: any) {
      error.value = err.message || 'Failed to delete swagger source'
      throw err
    }
  }

  return {
    swaggers,
    isLoading,
    error,
    fetchSwaggers,
    uploadSwagger,
    uploadSwaggerFromUrl,
    deleteSwagger,
  }
})
