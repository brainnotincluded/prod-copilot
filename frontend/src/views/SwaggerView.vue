<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useSwaggerStore } from '@/stores/swagger'
import { useLocale } from '@/composables/useLocale'
import SwaggerUpload from '@/components/swagger/SwaggerUpload.vue'
import SwaggerList from '@/components/swagger/SwaggerList.vue'

const swaggerStore = useSwaggerStore()
const { t } = useLocale()

const sourceCount = computed(() => swaggerStore.swaggers.length)

onMounted(() => {
  swaggerStore.fetchSwaggers()
})

function refreshList() {
  swaggerStore.fetchSwaggers()
}
</script>

<template>
  <div class="swagger-view">
    <div class="swagger-container">
      <!-- Page Header -->
      <div class="page-header">
        <div class="page-title-row">
          <h1 class="page-title">{{ t('swagger.title') }}</h1>
          <span v-if="sourceCount > 0" class="page-count">{{ sourceCount }}</span>
        </div>
        <p class="page-description">{{ t('swagger.description') }}</p>
      </div>

      <!-- Upload Card -->
      <div class="section-card">
        <div class="card-header">
          <h2 class="card-title">{{ t('swagger.addSpec') }}</h2>
        </div>
        <SwaggerUpload />
      </div>

      <!-- Sources List -->
      <div class="section">
        <div class="section-header">
          <h2 class="section-title">{{ t('swagger.connectedSources') }}</h2>
          <button class="refresh-btn" @click="refreshList" :title="t('swagger.refresh')">
            <i class="pi pi-refresh" :class="{ 'pi-spin': swaggerStore.isLoading }"></i>
          </button>
        </div>
        <SwaggerList
          :swaggers="swaggerStore.swaggers"
          :loading="swaggerStore.isLoading"
          @delete="swaggerStore.deleteSwagger"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.swagger-view {
  flex: 1;
  overflow-y: auto;
  padding: 32px 20px;
}

.swagger-container {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

/* Page Header */
.page-header {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.page-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text-primary);
  letter-spacing: -0.3px;
}

.page-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 24px;
  padding: 0 8px;
  border-radius: var(--radius-full);
  background: var(--color-accent-light);
  color: var(--color-accent);
  font-size: 12px;
  font-weight: 700;
}

.page-description {
  font-size: 14px;
  color: var(--color-text-secondary);
  line-height: 1.5;
}

/* Upload Card */
.section-card {
  background: var(--color-bg);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-x: auto;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

/* Sources Section */
.section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.refresh-btn {
  width: 44px;
  height: 44px;
  border: 1px solid var(--color-border-light);
  background: var(--color-bg);
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: background var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast);
  min-height: 44px;
  min-width: 44px;
  touch-action: manipulation;
}

.refresh-btn:hover {
  background: var(--color-bg-secondary);
  border-color: var(--color-border);
  color: var(--color-text-primary);
}

.refresh-btn:active {
  transform: scale(0.96);
}

/* Tablet (< 768px) */
@media (max-width: 768px) {
  .swagger-view {
    padding: 24px 16px;
  }

  .swagger-container {
    max-width: 100%;
    gap: 22px;
  }

  .page-title {
    font-size: 20px;
  }

  .page-description {
    font-size: 13px;
  }

  .section-card {
    padding: 18px 16px;
  }

  .card-title,
  .section-title {
    font-size: 14px;
  }
}

/* Mobile (< 640px) */
@media (max-width: 640px) {
  .swagger-view {
    padding: 16px 12px;
  }

  .swagger-container {
    gap: 20px;
    max-width: 100%;
  }

  /* Section cards - full width на мобильных */
  .section-card {
    padding: 16px 12px;
    border-radius: var(--radius-lg);
  }

  .page-header {
    gap: 4px;
  }

  .page-title {
    font-size: 18px;
  }

  .page-count {
    min-width: 26px;
    height: 26px;
    font-size: 12px;
  }

  /* Скрываем description на маленьких экранах для экономии места */
  .page-description {
    display: none;
  }

  .card-title,
  .section-title {
    font-size: 14px;
  }

  /* Touch-friendly кнопки */
  .refresh-btn {
    width: 48px;
    height: 48px;
    font-size: 16px;
  }
}

/* Small mobile (< 375px) */
@media (max-width: 375px) {
  .swagger-view {
    padding: 12px 10px;
  }

  .section-card {
    padding: 14px 10px;
  }

  .page-title {
    font-size: 17px;
  }

  .swagger-container {
    gap: 16px;
  }
}
</style>
