import { ref, onMounted, onUnmounted } from 'vue'

export interface MlStatus {
  status: 'ok' | 'degraded' | 'error'
  db: 'ok' | 'error'
  mlops: 'ok' | 'error'
  version: string
}

export function useMlStatus(pollInterval = 30000) {
  const mlStatus = ref<MlStatus | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  let intervalId: number | null = null

  async function checkStatus() {
    isLoading.value = true
    error.value = null
    
    try {
      const resp = await fetch('/health', {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
      })
      
      if (!resp.ok) {
        // Если сервер отвечает но с ошибкой - парсим ответ
        const data = await resp.json().catch(() => null)
        mlStatus.value = data || { 
          status: 'error', 
          db: 'error', 
          mlops: 'error',
          version: 'unknown'
        }
        return
      }
      
      mlStatus.value = await resp.json()
    } catch (err) {
      // Если сервер вообще не отвечает
      error.value = 'backend_unavailable'
      mlStatus.value = {
        status: 'error',
        db: 'error',
        mlops: 'error',
        version: 'unknown'
      }
    } finally {
      isLoading.value = false
    }
  }

  function startPolling() {
    checkStatus() // Первый запрос сразу
    intervalId = window.setInterval(checkStatus, pollInterval)
  }

  function stopPolling() {
    if (intervalId !== null) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  onMounted(startPolling)
  onUnmounted(stopPolling)

  return {
    mlStatus,
    isLoading,
    error,
    checkStatus,
    startPolling,
    stopPolling,
    // Удобные computed-свойства
    isMlAvailable: () => mlStatus.value?.mlops === 'ok',
    isFullyOperational: () => mlStatus.value?.status === 'ok',
    isDegraded: () => mlStatus.value?.status === 'degraded',
    isUnavailable: () => mlStatus.value?.status === 'error' || !mlStatus.value,
  }
}
