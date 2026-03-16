<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useQueryStore } from '@/stores/query'
import { useSwaggerStore } from '@/stores/swagger'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import ChatInput from '@/components/chat/ChatInput.vue'

const chatStore = useChatStore()
const queryStore = useQueryStore()
const swaggerStore = useSwaggerStore()
const messagesContainer = ref<HTMLElement | null>(null)

onMounted(() => {
  swaggerStore.fetchSwaggers()
})

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
        <h2 class="empty-title">Чем могу помочь?</h2>
        <p class="empty-subtitle">
          Задайте вопрос о ваших API. Я выполню запросы и верну структурированные результаты.
        </p>
        <div class="empty-suggestions">
          <button
            class="suggestion-chip"
            @click="handleSend('Покажи все доступные API эндпоинты')"
          >
            Покажи все доступные API эндпоинты
          </button>
          <button
            class="suggestion-chip"
            @click="handleSend('Покажи самые используемые эндпоинты за неделю')"
          >
            Покажи самые используемые эндпоинты за неделю
          </button>
          <button
            class="suggestion-chip"
            @click="handleSend('Найди пользователей, созданных за последние 24 часа')"
          >
            Найди пользователей, созданных за последние 24 часа
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
</style>
