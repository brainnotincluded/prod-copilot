import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useChatStore } from './chat'
import { useWebSocket } from '@/composables/useWebSocket'
import { useLocale } from '@/composables/useLocale'
import type { OrchestrationStep, QueryResult, WebSocketMessage } from '@/types'

// Save message to backend history (fire-and-forget)
async function saveToHistory(conversationId: number, role: string, content: string | null, resultData?: any) {
  try {
    const token = localStorage.getItem('auth_token')
    if (!token || !conversationId) return
    await fetch(`/api/v1/history/conversations/${conversationId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ role, content, result_data: resultData || null }),
    })
  } catch {
    // fire-and-forget
  }
}

async function createConversation(title: string): Promise<number | null> {
  try {
    const token = localStorage.getItem('auth_token')
    if (!token) return null
    const resp = await fetch('/api/v1/history/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ title }),
    })
    if (!resp.ok) return null
    const data = await resp.json()
    return data.id
  } catch {
    return null
  }
}

export const useQueryStore = defineStore('query', () => {
  const { t } = useLocale()
  const orchestrationSteps = ref<OrchestrationStep[]>([])
  const currentResult = ref<QueryResult | null>(null)
  const isLoading = ref(false)
  const currentMessageId = ref<string | null>(null)
  const selectedSourceIds = ref<number[]>([])
  const conversationId = ref<number | null>(null)

  const { send, onMessage, isConnected } = useWebSocket('/api/v1/ws/query')

  onMessage((msg: WebSocketMessage) => {
    const chatStore = useChatStore()

    switch (msg.type) {
      case 'chat_token': {
        const token = msg.data.token as string
        if (currentMessageId.value && token) {
          chatStore.appendToMessage(currentMessageId.value, token)
        }
        break
      }
      case 'step': {
        const step = msg.data as OrchestrationStep
        const existingIdx = orchestrationSteps.value.findIndex(
          (s) => s.step === step.step
        )
        if (existingIdx !== -1) {
          orchestrationSteps.value[existingIdx] = step
        } else {
          orchestrationSteps.value.push(step)
        }
        if (currentMessageId.value) {
          chatStore.updateMessage(currentMessageId.value, {
            steps: [...orchestrationSteps.value],
          })
        }
        break
      }
      case 'result': {
        currentResult.value = msg.data as QueryResult
        if (currentMessageId.value) {
          const isChatMode = currentResult.value.metadata?.mode === 'chat'
          const textContent = currentResult.value.data?.content || currentResult.value.data?.text || ''
          const hasRealData = currentResult.value.data && Object.keys(currentResult.value.data).length > 0
          const contentValue = currentResult.value.data?.content
          const isEmptyContent = contentValue === '' || contentValue === '{}' || contentValue === 'null' || contentValue === '[]'
          const isEmptyData = !hasRealData ||
            (Object.keys(currentResult.value.data).length === 1 && isEmptyContent)

          let finalContent = ''
          if (isChatMode) {
            finalContent = textContent
            chatStore.updateMessage(currentMessageId.value, {
              result: undefined,
              steps: [],
              content: textContent,
            })
          } else if (isEmptyData) {
            finalContent = textContent || t('error.noData')
            chatStore.updateMessage(currentMessageId.value, {
              result: undefined,
              content: finalContent,
            })
          } else {
            const summary = currentResult.value.metadata?.summary || ''
            let dataHint = summary
            const rows = currentResult.value.data?.rows
            if (rows && Array.isArray(rows)) {
              dataHint += ` (${rows.length} rows returned)`
            }
            finalContent = dataHint
            chatStore.updateMessage(currentMessageId.value, {
              result: currentResult.value,
              content: dataHint,
            })
          }

          // Save assistant response to history (include steps for replay)
          if (conversationId.value) {
            const historyData: any = {}
            if (!isChatMode && !isEmptyData && currentResult.value) {
              historyData.result = currentResult.value
            }
            if (orchestrationSteps.value.length > 0) {
              historyData.steps = orchestrationSteps.value
            }
            saveToHistory(
              conversationId.value,
              'assistant',
              finalContent || null,
              Object.keys(historyData).length > 0 ? historyData : undefined,
            )
          }
        }
        isLoading.value = false
        break
      }
      case 'error': {
        if (currentMessageId.value) {
          chatStore.updateMessage(currentMessageId.value, {
            content: `Error: ${msg.data.message || t('error.generic')}`,
          })
        }
        isLoading.value = false
        break
      }
      case 'done': {
        isLoading.value = false
        currentMessageId.value = null
        break
      }
    }
  })

  async function sendQuery(text: string, sourceIds?: number[]) {
    const chatStore = useChatStore()

    if (sourceIds !== undefined) {
      selectedSourceIds.value = sourceIds
    }

    // Create conversation on first message
    if (!conversationId.value) {
      const id = await createConversation(text.slice(0, 80))
      conversationId.value = id
    }

    const userMessage = {
      id: chatStore.generateId(),
      role: 'user' as const,
      content: text,
      timestamp: new Date(),
    }
    chatStore.addMessage(userMessage)

    // Save user message to history
    if (conversationId.value) {
      saveToHistory(conversationId.value, 'user', text)
    }

    const assistantId = chatStore.generateId()
    const assistantMessage = {
      id: assistantId,
      role: 'assistant' as const,
      content: '',
      steps: [],
      timestamp: new Date(),
    }
    chatStore.addMessage(assistantMessage)

    currentMessageId.value = assistantId
    orchestrationSteps.value = []
    currentResult.value = null
    isLoading.value = true

    const recentMessages = chatStore.messages
      .slice(-10)
      .filter(m => m.content)
      .map(m => ({ role: m.role, content: m.content }))

    const payload: Record<string, any> = { query: text, history: recentMessages }
    const ids = sourceIds !== undefined ? sourceIds : selectedSourceIds.value
    if (ids.length > 0) {
      payload.swagger_source_ids = ids
    }

    send(payload)
  }

  function startNewConversation() {
    conversationId.value = null
    useChatStore().clearChat()
  }

  return {
    orchestrationSteps,
    currentResult,
    isLoading,
    isConnected,
    selectedSourceIds,
    conversationId,
    sendQuery,
    startNewConversation,
  }
})
