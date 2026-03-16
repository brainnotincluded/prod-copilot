import axios, { type AxiosInstance } from 'axios'
import { useAuth } from './useAuth'
import router from '@/router'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

let instance: AxiosInstance | null = null

function createApiInstance(): AxiosInstance {
  const api = axios.create({
    baseURL: `${API_BASE_URL}/api/v1`,
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
  })

  // Add request interceptor to inject auth headers
  api.interceptors.request.use(
    (config) => {
      const { getAuthHeaders } = useAuth()
      const authHeaders = getAuthHeaders()
      
      // Merge auth headers into request
      Object.entries(authHeaders).forEach(([key, value]) => {
        config.headers[key] = value
      })
      
      return config
    },
    (error) => Promise.reject(error)
  )

  api.interceptors.response.use(
    (response) => response,
    async (error) => {
      // Handle authentication errors
      if (error.response?.status === 401) {
        const { logout } = useAuth()
        await logout()
        return Promise.reject(new Error('Session expired. Please sign in again.'))
      }
      
      // Handle authorization errors
      if (error.response?.status === 403) {
        const message = error.response?.data?.detail || 
          'You do not have permission to perform this action'
        return Promise.reject(new Error(message))
      }
      
      const message =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        'An unexpected error occurred'
      return Promise.reject(new Error(message))
    }
  )

  return api
}

export function useApi() {
  if (!instance) {
    instance = createApiInstance()
  }

  return {
    api: instance,
  }
}
