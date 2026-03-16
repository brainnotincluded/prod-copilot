<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  send: [text: string]
}>()

const inputText = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)

const canSend = computed(() => inputText.value.trim().length > 0 && !props.disabled)

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    send()
  }
}

function send() {
  if (!canSend.value) return
  emit('send', inputText.value.trim())
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
    <div class="chat-input-container">
      <textarea
        ref="textareaRef"
        v-model="inputText"
        class="chat-textarea"
        placeholder="Ask about your APIs..."
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
        title="Send message"
      >
        <i class="pi pi-arrow-up"></i>
      </button>
    </div>
    <p class="input-hint">
      Enter to send, Shift+Enter for new line
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
