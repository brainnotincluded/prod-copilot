<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useSwaggerStore } from '@/stores/swagger'
import { useLocale } from '@/composables/useLocale'

const props = defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  send: [text: string, sourceIds: number[]]
}>()

const swaggerStore = useSwaggerStore()
const { t } = useLocale()

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
  
  // Handle mobile keyboard appearance
  setupViewportHandler()
})

function setupViewportHandler() {
  // Check if it's a touch device
  const isTouchDevice = window.matchMedia('(pointer: coarse)').matches
  
  if (isTouchDevice && 'visualViewport' in window) {
    const viewport = window.visualViewport
    
    if (viewport) {
      viewport.addEventListener('resize', () => {
        // Scroll to keep input visible when keyboard appears
        if (document.activeElement === textareaRef.value) {
          setTimeout(() => {
            textareaRef.value?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
          }, 100)
        }
      })
    }
  }
}

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
      <div class="source-selector-scroll">
        <button
          class="source-chip"
          :class="{ selected: allSelected }"
          @click="toggleAll"
        >
          <span class="source-dot" :class="{ active: allSelected }"></span>
          <span class="source-name">{{ t('chat.allApis') }}</span>
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
      <!-- Fade effects for scroll -->
      <div class="source-selector-fade source-selector-fade-left"></div>
      <div class="source-selector-fade source-selector-fade-right"></div>
    </div>

    <div class="chat-input-container">
      <textarea
        ref="textareaRef"
        v-model="inputText"
        class="chat-textarea"
        :placeholder="t('chat.placeholder')"
        rows="1"
        :disabled="disabled"
        @keydown="handleKeydown"
        @input="handleInput"
        enterkeyhint="send"
      ></textarea>
      <button
        class="send-btn"
        :class="{ active: canSend }"
        :disabled="!canSend"
        @click="send"
        :title="t('chat.send')"
      >
        <i class="pi pi-arrow-up"></i>
      </button>
    </div>
    <p class="input-hint">{{ t('chat.hint') }}</p>
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
  position: relative;
  margin-bottom: 10px;
}

.source-selector-scroll {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 4px;
}

.source-selector-fade {
  display: none;
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
  flex-shrink: 0;
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
  min-height: 20px;
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

/* Mobile adaptations (< 640px) */
@media (max-width: 640px) {
  .chat-input-wrapper {
    padding: 8px 12px 8px;
    max-width: 100%;
  }

  /* Source selector - horizontal scroll with fade */
  .source-selector {
    position: relative;
    margin-bottom: 8px;
    overflow: hidden;
  }

  .source-selector-scroll {
    flex-wrap: nowrap;
    overflow-x: auto;
    padding: 2px 4px;
    gap: 6px;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    -ms-overflow-style: none;
  }

  .source-selector-scroll::-webkit-scrollbar {
    display: none;
  }

  .source-selector-fade {
    display: block;
    position: absolute;
    top: 0;
    bottom: 0;
    width: 24px;
    pointer-events: none;
    z-index: 1;
  }

  .source-selector-fade-left {
    left: 0;
    background: linear-gradient(to right, var(--color-bg) 0%, transparent 100%);
  }

  .source-selector-fade-right {
    right: 0;
    background: linear-gradient(to left, var(--color-bg) 0%, transparent 100%);
  }

  .source-chip {
    padding: 6px 12px;
    font-size: 13px;
  }

  .source-name {
    max-width: 120px;
  }

  /* Input container - full width */
  .chat-input-container {
    padding: 8px 10px 8px 16px;
    border-radius: 22px;
    gap: 6px;
  }

  /* Textarea - larger touch target */
  .chat-textarea {
    font-size: 16px; /* Prevents iOS zoom on focus */
    min-height: 44px;
    padding: 8px 0;
    line-height: 1.4;
  }

  /* Send button - larger for touch */
  .send-btn {
    width: 44px;
    height: 44px;
    min-width: 44px;
    min-height: 44px;
  }

  .send-btn i {
    font-size: 16px;
  }

  /* Hide hint on very small screens */
  .input-hint {
    display: none;
  }
}

/* Extra small screens (< 380px) */
@media (max-width: 380px) {
  .chat-input-wrapper {
    padding: 6px 8px 6px;
  }

  .chat-input-container {
    padding: 6px 8px 6px 12px;
  }

  .chat-textarea {
    font-size: 16px;
    min-height: 40px;
  }

  .send-btn {
    width: 40px;
    height: 40px;
    min-width: 40px;
    min-height: 40px;
  }
}

/* Tablet adaptations (641px - 768px) */
@media (max-width: 768px) and (min-width: 641px) {
  .chat-input-wrapper {
    padding: 10px 16px 8px;
  }
}
</style>
