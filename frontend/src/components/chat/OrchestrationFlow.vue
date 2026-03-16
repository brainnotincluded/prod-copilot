<script setup lang="ts">
import type { OrchestrationStep } from '@/types'

defineProps<{
  steps: OrchestrationStep[]
}>()

function statusIcon(status: string): string {
  switch (status) {
    case 'completed':
      return 'pi-check'
    case 'running':
      return 'pi-spin pi-spinner'
    case 'error':
      return 'pi-times'
    case 'pending':
    default:
      return 'pi-circle'
  }
}
</script>

<template>
  <div class="orchestration-flow">
    <div v-if="steps.length === 0" class="flow-empty">
      Нет шагов оркестрации
    </div>
    <div v-else class="timeline">
      <div
        v-for="(step, index) in steps"
        :key="step.step"
        class="timeline-item"
        :class="step.status"
      >
        <div class="timeline-indicator">
          <div class="timeline-dot" :class="step.status">
            <i class="pi" :class="statusIcon(step.status)"></i>
          </div>
          <div v-if="index < steps.length - 1" class="timeline-line" :class="step.status"></div>
        </div>
        <div class="timeline-content">
          <div class="step-header">
            <span class="step-number">{{ step.step }}</span>
            <span class="step-description-text" v-if="step.description">{{ step.description }}</span>
            <span class="step-description-text" v-else>{{ step.action }}</span>
          </div>
          <div v-if="step.description && step.action" class="step-action-badge">{{ step.action }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.orchestration-flow {
  padding: 12px 0;
}

.flow-empty {
  padding: 16px;
  text-align: center;
  color: var(--color-text-tertiary);
  font-size: 13px;
}

.timeline {
  display: flex;
  flex-direction: column;
}

.timeline-item {
  display: flex;
  gap: 10px;
  min-height: 40px;
}

.timeline-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 24px;
}

.timeline-dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background var(--transition-fast), border-color var(--transition-fast);
}

.timeline-dot i {
  font-size: 9px;
}

.timeline-dot.pending {
  background: var(--color-bg-tertiary);
  color: var(--color-text-tertiary);
  border: 1.5px solid var(--color-border);
}

.timeline-dot.running {
  background: var(--color-accent-light);
  color: var(--color-accent);
  border: 1.5px solid var(--color-accent);
  animation: dotPulse 2s ease-in-out infinite;
}

.timeline-dot.completed {
  background: #e6f4ea;
  color: var(--color-success);
  border: 1.5px solid var(--color-success);
}

.timeline-dot.error {
  background: #fce8e6;
  color: var(--color-error);
  border: 1.5px solid var(--color-error);
}

@keyframes dotPulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(26, 115, 232, 0.3);
  }
  50% {
    box-shadow: 0 0 0 4px rgba(26, 115, 232, 0);
  }
}

.timeline-line {
  width: 1.5px;
  flex: 1;
  min-height: 12px;
  background: var(--color-border);
  transition: background var(--transition-fast);
}

.timeline-line.completed {
  background: var(--color-success);
}

.timeline-line.running {
  background: var(--color-accent);
}

.timeline-content {
  padding-bottom: 12px;
  min-width: 0;
  flex: 1;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 6px;
  line-height: 20px;
}

.step-number {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-tertiary);
  min-width: 14px;
}

.step-description-text {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
  line-height: 1.4;
}

.timeline-item.running .step-description-text {
  color: var(--color-accent);
}

.timeline-item.error .step-description-text {
  color: var(--color-error);
}

.step-action-badge {
  display: inline-block;
  font-size: 10px;
  background: var(--color-bg-tertiary);
  padding: 1px 6px;
  border-radius: 4px;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-top: 4px;
}
</style>
