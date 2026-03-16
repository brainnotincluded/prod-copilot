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
  width: 32px;
  height: 32px;
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
}

.refresh-btn:hover {
  background: var(--color-bg-secondary);
  border-color: var(--color-border);
  color: var(--color-text-primary);
}

@media (max-width: 640px) {
  .swagger-view {
    padding: 20px 12px;
  }

  .swagger-container {
    gap: 20px;
  }

  .section-card {
    padding: 16px;
  }

  .page-title {
    font-size: 20px;
  }
}
</style>
