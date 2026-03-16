<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useSwaggerStore } from '@/stores/swagger'

const props = defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  send: [text: string, sourceIds: number[]]
}>()

const swaggerStore = useSwaggerStore()

const inputText = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const selectedSourceIds = ref<number[]>([])
const allSelected = ref(true)

const canSend = computed(() => inputText.value.trim().length > 0 && !props.disabled)
const sources = computed(() => swaggerStore.swaggers)
const hasSources = computed(() => sources.value.length > 0)

onMounted(() => {
  if (swaggerStore.swaggers.length === 0) {
    swaggerStore.fetchSwaggers()
  }
})

watch(
  () => swaggerStore.swaggers,
  (newSwaggers) => {
    // If "all" is selected, keep it that way
    if (allSelected.value) {
      selectedSourceIds.value = []
    }
  },
)

function toggleAll() {
  allSelected.value = true
  selectedSourceIds.value = []
}

function toggleSource(id: number) {
  allSelected.value = false
  const idx = selectedSourceIds.value.indexOf(id)
  if (idx !== -1) {
    selectedSourceIds.value.splice(idx, 1)
    // If nothing selected, revert to "all"
    if (selectedSourceIds.value.length === 0) {
      allSelected.value = true
    }
  } else {
    selectedSourceIds.value.push(id)
    // If all individual sources selected, switch to "all"
    if (selectedSourceIds.value.length === sources.value.length) {
      allSelected.value = true
      selectedSourceIds.value = []
    }
  }
}

function isSourceSelected(id: number): boolean {
  return allSelected.value || selectedSourceIds.value.includes(id)
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    send()
  }
}

function send() {
  if (!canSend.value) return
  emit('send', inputText.value.trim(), allSelected.value ? [] : [...selectedSourceIds.value])
  inputText.value = ''
  resizeTextarea()
}

function resizeTextarea() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 200) + 'px'
}

function handleInput() {
  resizeTextarea()
}
</script>

<template>
  <div class="chat-input-wrapper">
    <!-- API source selector chips -->
    <div v-if="hasSources" class="source-selector">
      <button
        class="source-chip"
        :class="{ selected: allSelected }"
        @click="toggleAll"
      >
        <span class="source-dot" :class="{ active: allSelected }"></span>
        <span class="source-name">Все API</span>
      </button>
      <button
        v-for="source in sources"
        :key="source.id"
        class="source-chip"
        :class="{ selected: isSourceSelected(source.id) && !allSelected }"
        @click="toggleSource(source.id)"
      >
        <span class="source-dot" :class="{ active: isSourceSelected(source.id) }"></span>
        <span class="source-name">{{ source.name }}</span>
      </button>
    </div>

    <div class="chat-input-container">
      <textarea
        ref="textareaRef"
        v-model="inputText"
        class="chat-textarea"
        placeholder="Задайте вопрос о ваших API..."
        rows="1"
        :disabled="disabled"
        @keydown="handleKeydown"
        @input="handleInput"
      ></textarea>
      <button
        class="send-btn"
        :class="{ active: canSend }"
        :disabled="!canSend"
        @click="send"
        title="Отправить сообщение"
      >
        <i class="pi pi-arrow-up"></i>
      </button>
    </div>
    <p class="input-hint">
      Enter для отправки, Shift+Enter для новой строки
    </p>
  </div>
</template>

<style scoped>
.chat-input-wrapper {
  padding: 12px 24px 10px;
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
}

/* Source selector */
.source-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
  padding: 0 4px;
}

.source-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
}

.source-chip:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.source-chip.selected {
  border-color: var(--color-accent);
  background: var(--color-accent-light);
  color: var(--color-accent);
}

.source-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-border);
  flex-shrink: 0;
  transition: background var(--transition-fast);
}

.source-dot.active {
  background: var(--color-accent);
}

.source-name {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-input-container {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  padding: 6px 8px 6px 20px;
  box-shadow: var(--shadow-input);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.chat-input-container:focus-within {
  border-color: var(--color-accent);
  box-shadow: var(--shadow-input), 0 0 0 1px var(--color-accent-light);
}

.chat-textarea {
  flex: 1;
  border: none;
  background: none;
  outline: none;
  resize: none;
  font-size: 14px;
  line-height: 1.5;
  color: var(--color-text-primary);
  padding: 6px 0;
  max-height: 200px;
}

.chat-textarea::placeholder {
  color: var(--color-text-tertiary);
}

.chat-textarea:disabled {
  opacity: 0.6;
}

.send-btn {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  background: var(--color-border);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition-fast), transform var(--transition-fast);
  flex-shrink: 0;
}

.send-btn.active {
  background: var(--color-accent);
}

.send-btn.active:hover {
  background: var(--color-accent-hover);
  transform: scale(1.05);
}

.send-btn:disabled {
  cursor: default;
}

.send-btn i {
  font-size: 13px;
}

.input-hint {
  text-align: center;
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}
</style>
