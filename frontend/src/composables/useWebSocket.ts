import { ref, onUnmounted } from 'vue'
import type { WebSocketMessage } from '@/types'

type MessageHandler = (message: WebSocketMessage) => void

export function useWebSocket(url: string) {
  const isConnected = ref(false)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 10
  const reconnectDelay = 2000

  let ws: WebSocket | null = null
  let handlers: MessageHandler[] = []
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function getWsUrl(): string {
    const token = localStorage.getItem('auth_token') || ''
    let wsUrl: string
    if (url.startsWith('ws://') || url.startsWith('wss://')) {
      // Full URL provided — use as-is
      wsUrl = url
    } else {
      // Relative path — build from current host
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      wsUrl = `${protocol}//${window.location.host}${url}`
    }
    const separator = wsUrl.includes('?') ? '&' : '?'
    return token ? `${wsUrl}${separator}token=${token}` : wsUrl
  }

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    const wsUrl = getWsUrl()
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      isConnected.value = true
      reconnectAttempts.value = 0
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data)
        handlers.forEach((handler) => handler(message))
      } catch {
        console.warn('Failed to parse WebSocket message:', event.data)
      }
    }

    ws.onclose = () => {
      isConnected.value = false
      scheduleReconnect()
    }

    ws.onerror = () => {
      isConnected.value = false
    }
  }

  function scheduleReconnect() {
    if (reconnectAttempts.value >= maxReconnectAttempts) {
      return
    }

    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
    }

    reconnectTimer = setTimeout(() => {
      reconnectAttempts.value++
      connect()
    }, reconnectDelay * Math.min(reconnectAttempts.value + 1, 5))
  }

  function send(data: any) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      connect()
      setTimeout(() => send(data), 500)
      return
    }
    ws.send(JSON.stringify(data))
  }

  function onMessage(handler: MessageHandler) {
    handlers.push(handler)
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.close()
      ws = null
    }
    isConnected.value = false
  }

  connect()

  onUnmounted(() => {
    disconnect()
  })

  return {
    isConnected,
    send,
    onMessage,
    disconnect,
  }
}
