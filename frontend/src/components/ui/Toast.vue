<script setup lang="ts">
import { useToast } from '@/composables/useToast'

const { toasts, removeToast } = useToast()
</script>

<template>
  <Teleport to="body">
    <TransitionGroup name="toast" tag="div" class="toast-container">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="toast-item"
        :class="toast.type"
        @click="removeToast(toast.id)"
      >
        <i
          class="pi toast-icon"
          :class="{
            'pi-check-circle': toast.type === 'success',
            'pi-exclamation-circle': toast.type === 'error',
            'pi-info-circle': toast.type === 'info',
          }"
        ></i>
        <span class="toast-message">{{ toast.message }}</span>
        <button class="toast-close" @click.stop="removeToast(toast.id)">
          <i class="pi pi-times"></i>
        </button>
      </div>
    </TransitionGroup>
  </Teleport>
</template>

<style scoped>
.toast-container {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 10000;
  display: flex;
  flex-direction: column-reverse;
  gap: 8px;
  max-width: 400px;
}

.toast-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  cursor: pointer;
  font-size: 13px;
  line-height: 1.4;
  min-width: 280px;
  border: 1px solid;
}

.toast-item.success {
  background: #f0faf3;
  color: #1e7e34;
  border-color: #c3e6cb;
}

.toast-item.error {
  background: #fde7e7;
  color: #c62828;
  border-color: #f5c6cb;
}

.toast-item.info {
  background: #e8f0fe;
  color: #1558b0;
  border-color: #b6d4fe;
}

.toast-icon {
  font-size: 16px;
  flex-shrink: 0;
  margin-top: 1px;
}

.toast-message {
  flex: 1;
}

.toast-close {
  background: none;
  border: none;
  color: inherit;
  opacity: 0.5;
  cursor: pointer;
  padding: 0;
  font-size: 12px;
  flex-shrink: 0;
  margin-top: 1px;
}

.toast-close:hover {
  opacity: 1;
}

/* Transitions */
.toast-enter-active {
  transition: all 0.3s ease-out;
}

.toast-leave-active {
  transition: all 0.2s ease-in;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(40px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(40px);
}

.toast-move {
  transition: transform 0.3s ease;
}

@media (max-width: 640px) {
  .toast-container {
    left: 12px;
    right: 12px;
    bottom: 12px;
    max-width: none;
  }

  .toast-item {
    min-width: 0;
  }
}
</style>
