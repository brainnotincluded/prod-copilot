import axios, { type AxiosInstance } from 'axios'

let instance: AxiosInstance | null = null

function createApiInstance(): AxiosInstance {
  const api = axios.create({
    baseURL: '',
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
  })

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
