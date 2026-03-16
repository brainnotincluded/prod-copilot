import axios, { type AxiosInstance } from 'axios'
import { useAuth } from './useAuth'

let instance: AxiosInstance | null = null

function createApiInstance(): AxiosInstance {
  const api = axios.create({
    baseURL: '',
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
  })

  // Add request interceptor to inject X-User-Role header
  api.interceptors.request.use(
    (config) => {
      const { getRoleHeader } = useAuth()
      config.headers['X-User-Role'] = getRoleHeader()
      return config
    },
    (error) => Promise.reject(error)
  )

  api.interceptors.response.use(
    (response) => response,
    (error) => {
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
