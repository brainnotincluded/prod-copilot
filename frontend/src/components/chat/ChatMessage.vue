<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { marked } from 'marked'
import type { ChatMessage } from '@/types'
import { useLocale } from '@/composables/useLocale'
import OrchestrationFlow from './OrchestrationFlow.vue'
import ResultRenderer from '@/components/results/ResultRenderer.vue'

// Configure marked for safe inline rendering
marked.setOptions({ breaks: true, gfm: true })

const props = defineProps<{
  message: ChatMessage
}>()

const { t } = useLocale()
const showSteps = ref(false)
const showReasoning = ref(false)

const isUser = computed(() => props.message.role === 'user')
const hasReasoning = computed(() => !!props.message.reasoning)
const hasSteps = computed(
  () => props.message.steps && props.message.steps.length > 0
)
const hasResult = computed(() => {
  if (!props.message.result) return false
  const d = props.message.result.data
  if (!d || (typeof d === 'object' && Object.keys(d).length === 0)) return false
  return true
})
const hasContent = computed(() => {
  return typeof props.message.content === 'string' && props.message.content.length > 0
})
const isLoading = computed(() => {
  return !isUser.value && !hasContent.value && !hasResult.value
})

const renderedContent = computed(() => {
  if (!props.message.content) return ''
  return marked.parse(props.message.content) as string
})

const reasoningHtml = computed(() => {
  if (!props.message.reasoning) return ''
  return marked.parse(props.message.reasoning) as string
})

const stepsLabel = computed(() => {
  const steps = props.message.steps || []
  const total = steps.length
  const errors = steps.filter(s => s.status === 'error').length
  const allDone = steps.every(s => s.status === 'completed' || s.status === 'error')

  if (!allDone) {
    return t('chat.running', total)
  }
  if (errors > 0) {
    return t('chat.stepsFailed', total, errors)
  }
  return t('chat.stepsCompleted', total)
})
const formattedTime = computed(() => {
  const date = new Date(props.message.timestamp)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
})

// Auto-expand steps when loading (steps arriving but no result yet)
watch(
  () => hasSteps.value && !hasResult.value && !hasContent.value,
  (shouldExpand) => {
    if (shouldExpand) {
      showSteps.value = true
    }
  },
  { immediate: true }
)
</script>

<template>
  <div class="chat-message" :class="{ user: isUser, assistant: !isUser }">
    <div class="message-container">
      <div class="message-avatar">
        <span v-if="isUser" class="avatar user-avatar">
          <i class="pi pi-user"></i>
        </span>
        <span v-else class="avatar assistant-avatar">P</span>
      </div>

      <div class="message-body">
        <div class="message-header">
          <span class="message-role">{{ isUser ? t('chat.you') : t('chat.copilot') }}</span>
          <span class="message-time">{{ formattedTime }}</span>
        </div>

        <div class="message-content" v-if="hasContent" v-html="renderedContent"></div>

        <!-- Loading state: no content, no result, is assistant -->
        <div v-if="isLoading && !hasSteps" class="message-thinking">
          <div class="thinking-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span class="thinking-text">{{ t('chat.thinking') }}</span>
        </div>

        <!-- Model Reasoning (Chain of Thought) -->
        <div v-if="hasReasoning" class="message-reasoning">
          <button class="reasoning-toggle" @click="showReasoning = !showReasoning">
            <i class="pi" :class="showReasoning ? 'pi-chevron-down' : 'pi-chevron-right'"></i>
            <i class="pi pi-lightbulb reasoning-icon"></i>
            <span class="reasoning-label">{{ t('chat.reasoning') }}</span>
          </button>
          <transition name="steps-expand">
            <div v-if="showReasoning" class="reasoning-content">
              <div v-html="reasoningHtml"></div>
            </div>
          </transition>
        </div>

        <div v-if="hasSteps" class="message-steps">
          <button class="steps-toggle" @click="showSteps = !showSteps">
            <i
              class="pi"
              :class="showSteps ? 'pi-chevron-down' : 'pi-chevron-right'"
            ></i>
            <span class="steps-label">{{ stepsLabel }}</span>
            <span class="steps-status">
              <span
                v-for="step in message.steps"
                :key="step.step"
                class="step-dot"
                :class="step.status"
                :title="t('chat.stepTooltip', step.step, step.action, step.status)"
              ></span>
            </span>
          </button>

          <transition name="steps-expand">
            <div v-if="showSteps" class="steps-content">
              <OrchestrationFlow :steps="message.steps!" />
            </div>
          </transition>
        </div>

        <div v-if="hasResult" class="message-result result-fade-in">
          <ResultRenderer :result="message.result!" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-message {
  padding: 2px 24px;
}

.chat-message.user {
  background: var(--color-user-bg);
}

.chat-message.assistant {
  background: var(--color-assistant-bg);
}

.message-container {
  display: flex;
  gap: 12px;
  max-width: 800px;
  margin: 0 auto;
  padding: 16px 0;
}

.message-avatar {
  flex-shrink: 0;
  padding-top: 2px;
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}

.user-avatar {
  background: var(--color-bg-tertiary);
  color: var(--color-text-secondary);
}

.user-avatar i {
  font-size: 12px;
}

.assistant-avatar {
  background: var(--color-accent);
  color: white;
}

.message-body {
  flex: 1;
  min-width: 0;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.message-role {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.message-time {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.message-content {
  font-size: 14px;
  color: var(--color-text-primary);
  line-height: 1.6;
  word-wrap: break-word;
}

.message-content :deep(p) { margin: 0 0 8px 0; }
.message-content :deep(p:last-child) { margin-bottom: 0; }
.message-content :deep(code) {
  background: var(--color-bg-tertiary, #f5f5f5);
  padding: 1px 4px; border-radius: 3px;
  font-size: 0.9em; font-family: monospace;
}
.message-content :deep(pre) {
  background: var(--color-bg-tertiary, #f5f5f5);
  padding: 12px; border-radius: 6px; overflow-x: auto;
}
.message-content :deep(strong) { font-weight: 600; }
.message-content :deep(ul), .message-content :deep(ol) {
  padding-left: 20px; margin: 4px 0;
}
.message-content :deep(li) { margin: 2px 0; }
.message-content :deep(h1), .message-content :deep(h2), .message-content :deep(h3), .message-content :deep(h4) {
  margin: 8px 0 4px 0; font-weight: 600;
}
.message-content :deep(h1) { font-size: 1.3em; }
.message-content :deep(h2) { font-size: 1.15em; }
.message-content :deep(h3) { font-size: 1.05em; }

/* Thinking/loading state */
.message-thinking {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.thinking-dots {
  display: flex;
  gap: 3px;
}

.thinking-dots span {
  width: 5px;
  height: 5px;
  background: var(--color-text-tertiary);
  border-radius: 50%;
  animation: thinkingDot 1.4s infinite ease-in-out both;
}

.thinking-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.thinking-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes thinkingDot {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.4;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.thinking-text {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

/* Reasoning (CoT) */
.message-reasoning {
  margin-top: 8px;
}

.reasoning-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid #fbbc0440;
  border-radius: var(--radius-pill);
  background: #fbbc0410;
  color: #b8860b;
  font-size: 12px;
  transition: background var(--transition-fast);
  cursor: pointer;
}

.reasoning-toggle:hover {
  background: #fbbc0425;
}

.reasoning-toggle i {
  font-size: 9px;
  width: 10px;
}

.reasoning-icon {
  color: #fbbc04;
  font-size: 12px !important;
  width: auto !important;
}

.reasoning-label {
  font-weight: 500;
}

.reasoning-content {
  margin-top: 8px;
  padding: 10px 14px;
  background: #fbbc0408;
  border-left: 3px solid #fbbc04;
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.reasoning-content :deep(p) { margin: 0 0 6px 0; }
.reasoning-content :deep(p:last-child) { margin-bottom: 0; }
.reasoning-content :deep(strong) { color: var(--color-text-primary); }

/* Steps */
.message-steps {
  margin-top: 8px;
}

.steps-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-pill);
  background: var(--color-bg);
  color: var(--color-text-tertiary);
  font-size: 12px;
  transition: background var(--transition-fast), color var(--transition-fast);
  cursor: pointer;
}

.steps-toggle:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-secondary);
}

.steps-toggle i {
  font-size: 9px;
  width: 10px;
  transition: transform var(--transition-fast);
}

.steps-label {
  font-weight: 500;
}

.steps-status {
  display: flex;
  gap: 2px;
  margin-left: 2px;
}

.step-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-border);
}

.step-dot.completed {
  background: var(--color-success);
}

.step-dot.running {
  background: var(--color-running);
  animation: pulse 1.2s ease-in-out infinite;
}

.step-dot.error {
  background: var(--color-error);
}

.step-dot.pending {
  background: var(--color-border);
}

.steps-content {
  margin-top: 8px;
}

.message-result {
  margin-top: 12px;
}

/* Mobile adaptations (< 640px) */
@media (max-width: 640px) {
  .chat-message {
    padding: 4px 12px;
  }

  .message-container {
    gap: 10px;
    padding: 12px 0;
  }

  .message-avatar {
    padding-top: 1px;
  }

  .avatar {
    width: 24px;
    height: 24px;
    font-size: 10px;
  }

  .user-avatar i {
    font-size: 10px;
  }

  .message-header {
    gap: 6px;
    margin-bottom: 3px;
  }

  .message-role {
    font-size: 12px;
  }

  .message-time {
    font-size: 10px;
  }

  .message-content {
    font-size: 15px;
    line-height: 1.5;
  }

  .message-content :deep(pre) {
    padding: 10px;
    border-radius: 4px;
  }

  .message-content :deep(ul), .message-content :deep(ol) {
    padding-left: 16px;
  }

  /* Larger touch target for steps toggle */
  .steps-toggle {
    padding: 6px 12px;
    min-height: 36px;
  }

  .steps-toggle i {
    font-size: 10px;
  }

  .step-dot {
    width: 5px;
    height: 5px;
  }

  .message-result {
    margin-top: 10px;
  }

  .message-result :deep(.result-container) {
    border-radius: 8px;
  }

  .thinking-text {
    font-size: 12px;
  }
}

/* Tablet adaptations (641px - 768px) */
@media (max-width: 768px) and (min-width: 641px) {
  .chat-message {
    padding: 4px 16px;
  }

  .message-container {
    padding: 14px 0;
  }

  .avatar {
    width: 26px;
    height: 26px;
    font-size: 11px;
  }

  .user-avatar i {
    font-size: 11px;
  }
}
</style>
