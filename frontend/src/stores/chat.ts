import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatMessage } from '@/types'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])

  function addMessage(message: ChatMessage) {
    messages.value.push(message)
  }

  function updateMessage(id: string, updates: Partial<ChatMessage>) {
    const index = messages.value.findIndex((m) => m.id === id)
    if (index !== -1) {
      messages.value[index] = { ...messages.value[index], ...updates }
    }
  }

  function appendToMessage(id: string, text: string) {
    const msg = messages.value.find((m) => m.id === id)
    if (msg) {
      msg.content += text
    }
  }

  function clearChat() {
    messages.value = []
  }

  function generateId(): string {
    return Date.now().toString(36) + Math.random().toString(36).substring(2, 9)
  }

  return {
    messages,
    addMessage,
    updateMessage,
    appendToMessage,
    clearChat,
    generateId,
  }
})
