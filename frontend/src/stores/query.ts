import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useChatStore } from './chat'
import { useWebSocket } from '@/composables/useWebSocket'
import { useLocale } from '@/composables/useLocale'
import type { OrchestrationStep, QueryResult, WebSocketMessage } from '@/types'

export const useQueryStore = defineStore('query', () => {
  const { t } = useLocale()
  const orchestrationSteps = ref<OrchestrationStep[]>([])
  const currentResult = ref<QueryResult | null>(null)
  const isLoading = ref(false)
  const currentMessageId = ref<string | null>(null)
  const selectedSourceIds = ref<number[]>([])

  const { send, onMessage, isConnected } = useWebSocket('/api/ws/query')

  onMessage((msg: WebSocketMessage) => {
    const chatStore = useChatStore()

    switch (msg.type) {
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

          if (isChatMode) {
            // Chat mode: show text inline, hide steps and result renderer
            chatStore.updateMessage(currentMessageId.value, {
              result: undefined,
              steps: [],
              content: textContent,
            })
          } else if (isEmptyData) {
            // Empty result: show error text
            chatStore.updateMessage(currentMessageId.value, {
              result: undefined,
              content: textContent || t('error.noData'),
            })
          } else {
            // API result with data: show result renderer + optional summary text
            const summary = currentResult.value.metadata?.summary || ''
            chatStore.updateMessage(currentMessageId.value, {
              result: currentResult.value,
              content: summary,
            })
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

  function sendQuery(text: string, sourceIds?: number[]) {
    const chatStore = useChatStore()

    // Persist selected source IDs
    if (sourceIds !== undefined) {
      selectedSourceIds.value = sourceIds
    }

    const userMessage = {
      id: chatStore.generateId(),
      role: 'user' as const,
      content: text,
      timestamp: new Date(),
    }
    chatStore.addMessage(userMessage)

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

    // Include recent chat history for context
    const recentMessages = chatStore.messages
      .slice(-10)  // last 10 messages
      .filter(m => m.content)
      .map(m => ({ role: m.role, content: m.content }))

    const payload: Record<string, any> = { query: text, history: recentMessages }
    const ids = sourceIds !== undefined ? sourceIds : selectedSourceIds.value
    if (ids.length > 0) {
      payload.swagger_source_ids = ids
    }

    send(payload)
  }

  return {
    orchestrationSteps,
    currentResult,
    isLoading,
    isConnected,
    selectedSourceIds,
    sendQuery,
  }
})
