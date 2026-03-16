<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { useQueryStore } from '@/stores/query'
import { useSwaggerStore } from '@/stores/swagger'
import { useLocale } from '@/composables/useLocale'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import ChatInput from '@/components/chat/ChatInput.vue'

const chatStore = useChatStore()
const queryStore = useQueryStore()
const swaggerStore = useSwaggerStore()
const route = useRoute()
const { t } = useLocale()
const messagesContainer = ref<HTMLElement | null>(null)

onMounted(async () => {
  swaggerStore.fetchSwaggers()

  // Load conversation from history if ?conversation=ID is present
  const convId = route.query.conversation
  if (convId) {
    await loadConversation(Number(convId))
  }
})

async function loadConversation(id: number) {
  try {
    const token = localStorage.getItem('auth_token')
    if (!token) return
    const resp = await fetch(`/api/v1/history/conversations/${id}`, {
      headers: { 'Authorization': `Bearer ${token}` },
    })
    if (!resp.ok) return
    const data = await resp.json()

    // Clear current chat and load saved messages
    chatStore.clearChat()
    queryStore.conversationId = id

    for (const msg of data.messages) {
      const rd = msg.result_data || {}
      chatStore.addMessage({
        id: chatStore.generateId(),
        role: msg.role,
        content: msg.content || '',
        result: rd.result || undefined,
        steps: rd.steps || undefined,
        timestamp: new Date(msg.created_at),
      })
    }
  } catch {
    // ignore
  }
}

const hasMessages = computed(() => chatStore.messages.length > 0)

function handleSend(text: string, sourceIds: number[] = []) {
  queryStore.sendQuery(text, sourceIds)
  scrollToBottom()
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTo({
        top: messagesContainer.value.scrollHeight,
        behavior: 'smooth',
      })
    }
  })
}

// Scroll when new messages arrive
watch(
  () => chatStore.messages.length,
  () => scrollToBottom()
)

// Scroll when steps update or results come in
watch(
  () => chatStore.messages.map((m) => (m.steps?.length || 0) + (m.result ? 1 : 0) + (m.content?.length || 0)),
  () => scrollToBottom(),
  { deep: true }
)
</script>

<template>
  <div class="chat-view">
    <div v-if="!hasMessages" class="chat-empty">
      <div class="empty-content">
        <div class="empty-logo">P</div>
        <h2 class="empty-title">{{ t('chat.emptyTitle') }}</h2>
        <p class="empty-subtitle">{{ t('chat.emptySubtitle') }}</p>
        <div class="empty-suggestions">
          <button
            class="suggestion-chip"
            @click="handleSend(t('chat.suggestion1'))"
          >
            {{ t('chat.suggestion1') }}
          </button>
          <button
            class="suggestion-chip"
            @click="handleSend(t('chat.suggestion2'))"
          >
            {{ t('chat.suggestion2') }}
          </button>
          <button
            class="suggestion-chip"
            @click="handleSend(t('chat.suggestion3'))"
          >
            {{ t('chat.suggestion3') }}
          </button>
        </div>
      </div>
    </div>

    <div v-else ref="messagesContainer" class="chat-messages">
      <ChatMessage
        v-for="message in chatStore.messages"
        :key="message.id"
        :message="message"
      />
    </div>

    <div class="chat-input-area">
      <ChatInput @send="handleSend" :disabled="queryStore.isLoading" />
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-bg);
}

.chat-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}

.empty-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  max-width: 640px;
}

.empty-logo {
  width: 64px;
  height: 64px;
  background: var(--color-accent);
  color: white;
  border-radius: var(--radius-xl);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 28px;
}

.empty-title {
  font-size: 32px;
  font-weight: 400;
  color: var(--color-text-primary);
  letter-spacing: -0.5px;
}

.empty-subtitle {
  font-size: 16px;
  color: var(--color-text-secondary);
  text-align: center;
  line-height: 1.6;
  max-width: 480px;
}

.empty-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  margin-top: 8px;
}

.suggestion-chip {
  padding: 10px 18px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  background: var(--color-bg);
  color: var(--color-text-secondary);
  font-size: 13px;
  transition: background var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast);
  flex-shrink: 0;
}

.suggestion-chip:hover {
  background: var(--color-accent-light);
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.chat-input-area {
  flex-shrink: 0;
  background: var(--color-bg);
  border-top: 1px solid var(--color-border-light);
}

/* Mobile adaptations */
@media (max-width: 640px) {
  .chat-empty {
    padding: 20px 12px;
  }

  .empty-content {
    gap: 16px;
  }

  .empty-logo {
    width: 48px;
    height: 48px;
    font-size: 22px;
    border-radius: var(--radius-lg);
  }

  .empty-title {
    font-size: 24px;
    letter-spacing: -0.3px;
  }

  .empty-subtitle {
    font-size: 14px;
    line-height: 1.5;
    padding: 0 8px;
  }

  .empty-suggestions {
    flex-wrap: nowrap;
    justify-content: flex-start;
    overflow-x: auto;
    padding: 4px 12px;
    margin: 8px -12px 0;
    gap: 8px;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    -ms-overflow-style: none;
  }

  .empty-suggestions::-webkit-scrollbar {
    display: none;
  }

  .suggestion-chip {
    padding: 8px 14px;
    font-size: 12px;
  }

  .chat-messages {
    padding: 4px 0;
  }
}

/* Tablet adaptations */
@media (max-width: 768px) and (min-width: 641px) {
  .chat-empty {
    padding: 30px 16px;
  }

  .empty-logo {
    width: 56px;
    height: 56px;
    font-size: 24px;
  }

  .empty-title {
    font-size: 28px;
  }

  .empty-suggestions {
    gap: 8px;
  }
}
</style>
