<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '@/composables/useApi'

interface Conversation {
  id: number
  title: string
  created_at: string
  updated_at: string
  message_count: number
  preview: string | null
}

const { api } = useApi()
const router = useRouter()

const conversations = ref<Conversation[]>([])
const searchQuery = ref('')
const isLoading = ref(false)

const filteredConversations = computed(() => {
  if (!searchQuery.value) return conversations.value
  const q = searchQuery.value.toLowerCase()
  return conversations.value.filter(
    (c) =>
      c.title.toLowerCase().includes(q) ||
      (c.preview && c.preview.toLowerCase().includes(q))
  )
})

async function loadConversations() {
  isLoading.value = true
  try {
    const params: Record<string, string> = {}
    if (searchQuery.value) params.search = searchQuery.value
    const { data } = await api.get('/history/conversations', { params })
    conversations.value = data
  } catch {
    conversations.value = []
  } finally {
    isLoading.value = false
  }
}

async function openConversation(id: number) {
  router.push({ name: 'chat', query: { conversation: id } })
}

async function deleteConversation(id: number, event: Event) {
  event.stopPropagation()
  if (!confirm('Delete this conversation?')) return
  try {
    await api.delete(`/history/conversations/${id}`)
    conversations.value = conversations.value.filter((c) => c.id !== id)
  } catch {
    // ignore
  }
}

function formatDate(iso: string) {
  const d = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const days = Math.floor(diff / 86400000)
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days} days ago`
  return d.toLocaleDateString()
}

let searchTimeout: ReturnType<typeof setTimeout> | null = null
function onSearch() {
  if (searchTimeout) clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => loadConversations(), 300)
}

onMounted(loadConversations)
</script>

<template>
  <div class="history-view">
    <div class="history-header">
      <h2>Chat History</h2>
      <div class="search-box">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search conversations..."
          class="search-input"
          @input="onSearch"
        />
      </div>
    </div>

    <div v-if="isLoading" class="loading">Loading...</div>

    <div v-else-if="filteredConversations.length === 0" class="empty">
      <p v-if="searchQuery">No conversations matching "{{ searchQuery }}"</p>
      <p v-else>No conversations yet. Start chatting!</p>
    </div>

    <div v-else class="conversation-list">
      <div
        v-for="conv in filteredConversations"
        :key="conv.id"
        class="conversation-card"
        @click="openConversation(conv.id)"
      >
        <div class="conv-main">
          <div class="conv-title">{{ conv.title }}</div>
          <div class="conv-preview" v-if="conv.preview">{{ conv.preview }}</div>
        </div>
        <div class="conv-meta">
          <span class="conv-date">{{ formatDate(conv.updated_at) }}</span>
          <span class="conv-count">{{ conv.message_count }} msgs</span>
          <button class="conv-delete" @click="deleteConversation(conv.id, $event)" title="Delete">
            &times;
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.history-view {
  padding: 24px;
  max-width: 800px;
  margin: 0 auto;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  gap: 16px;
}

.history-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
}

.search-input {
  padding: 10px 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg);
  color: var(--color-text-primary);
  font-size: 14px;
  width: 300px;
  outline: none;
  transition: border-color var(--transition-fast);
}

.search-input:focus {
  border-color: var(--color-accent);
}

.loading,
.empty {
  text-align: center;
  color: var(--color-text-secondary);
  padding: 40px;
  font-size: 15px;
}

.conversation-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.conversation-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: background var(--transition-fast), border-color var(--transition-fast);
}

.conversation-card:hover {
  background: var(--color-accent-light);
  border-color: var(--color-accent);
}

.conv-main {
  flex: 1;
  min-width: 0;
}

.conv-title {
  font-weight: 500;
  font-size: 15px;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-preview {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  margin-left: 16px;
}

.conv-date,
.conv-count {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.conv-delete {
  width: 28px;
  height: 28px;
  border: none;
  background: none;
  color: var(--color-text-secondary);
  font-size: 18px;
  cursor: pointer;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.conv-delete:hover {
  color: #e74c3c;
  background: rgba(231, 76, 60, 0.1);
}
</style>
