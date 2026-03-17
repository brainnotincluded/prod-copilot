<script setup lang="ts">
import { computed } from 'vue'
import { useMlStatus } from '@/composables/useMlStatus'
import { useLocale } from '@/composables/useLocale'

const { mlStatus, isUnavailable, isDegraded } = useMlStatus(30000)
const { t } = useLocale()

const showBanner = computed(() => {
  return isUnavailable() || isDegraded()
})

const bannerType = computed(() => {
  if (isUnavailable()) return 'error'
  if (isDegraded()) return 'warning'
  return 'info'
})

const bannerIcon = computed(() => {
  if (isUnavailable()) return '⚠️'
  if (isDegraded()) return '⚡'
  return 'ℹ️'
})

const bannerTitle = computed(() => {
  if (isUnavailable()) return t('mlStatus.unavailableTitle')
  if (isDegraded()) return t('mlStatus.degradedTitle')
  return ''
})

const bannerMessage = computed(() => {
  if (!mlStatus.value) return t('mlStatus.checking')
  
  if (mlStatus.value.db === 'error' && mlStatus.value.mlops === 'error') {
    return t('mlStatus.allServicesDown')
  }
  
  if (mlStatus.value.mlops === 'error') {
    return t('mlStatus.mlopsDown')
  }
  
  if (mlStatus.value.db === 'error') {
    return t('mlStatus.dbDown')
  }
  
  return t('mlStatus.unknownIssue')
})

const canUseChat = computed(() => {
  // Чат можно использовать если хотя бы бэкенд работает
  return mlStatus.value?.db === 'ok'
})

const mlSpecificUnavailable = computed(() => {
  // ML специфически недоступен (бэкенд работает, но ML нет)
  return mlStatus.value?.db === 'ok' && mlStatus.value?.mlops === 'error'
})
</script>

<template>
  <div v-if="showBanner" class="ml-status-banner" :class="`banner-${bannerType}`">
    <div class="banner-content">
      <span class="banner-icon">{{ bannerIcon }}</span>
      <div class="banner-text">
        <strong>{{ bannerTitle }}</strong>
        <span>{{ bannerMessage }}</span>
      </div>
    </div>
    <div v-if="mlSpecificUnavailable" class="banner-hint">
      {{ t('mlStatus.basicFeaturesAvailable') }}
    </div>
  </div>
  
  <!-- Баннер для чата когда ML недоступен -->
  <div v-if="mlSpecificUnavailable" class="ml-chat-warning">
    <span class="warning-icon">🤖❌</span>
    <span class="warning-text">{{ t('mlStatus.mlUnavailableForChat') }}</span>
  </div>
</template>

<style scoped>
.ml-status-banner {
  padding: 12px 20px;
  border-radius: var(--radius-lg);
  margin: 0 20px 16px;
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.banner-error {
  background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
  border: 1px solid #f87171;
  color: #991b1b;
}

.banner-warning {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  border: 1px solid #fbbf24;
  color: #92400e;
}

.banner-info {
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  border: 1px solid #60a5fa;
  color: #1e40af;
}

.banner-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.banner-icon {
  font-size: 20px;
  flex-shrink: 0;
}

.banner-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.banner-text strong {
  font-weight: 600;
  font-size: 14px;
}

.banner-text span {
  font-size: 13px;
  opacity: 0.9;
}

.banner-hint {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed currentColor;
  opacity: 0.8;
  font-size: 12px;
}

.ml-chat-warning {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 16px;
  background: #fef3c7;
  border: 1px solid #fbbf24;
  border-radius: var(--radius-pill);
  margin: 0 20px 12px;
  color: #92400e;
  font-size: 13px;
}

.warning-icon {
  font-size: 16px;
}

.warning-text {
  font-weight: 500;
}

/* Мобильная адаптация */
@media (max-width: 640px) {
  .ml-status-banner {
    margin: 0 12px 12px;
    padding: 10px 14px;
  }
  
  .banner-content {
    gap: 10px;
  }
  
  .banner-icon {
    font-size: 18px;
  }
  
  .banner-text strong {
    font-size: 13px;
  }
  
  .banner-text span {
    font-size: 12px;
  }
  
  .ml-chat-warning {
    margin: 0 12px 10px;
    padding: 6px 12px;
    font-size: 12px;
  }
}
</style>
