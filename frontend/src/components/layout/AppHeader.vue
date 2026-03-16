<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useQueryStore } from '@/stores/query'
import { useLocale } from '@/composables/useLocale'

const props = defineProps<{
  sidebarCollapsed: boolean
}>()

const emit = defineEmits<{
  toggleSidebar: []
}>()

const route = useRoute()
const queryStore = useQueryStore()
const { t } = useLocale()

const pageTitle = computed(() => {
  switch (route.path) {
    case '/chat':
      return t('nav.chat')
    case '/swagger':
      return t('nav.apiSources')
    case '/dashboard':
      return t('nav.dashboard')
    case '/endpoints':
      return t('nav.apiMaps')
    case '/settings':
      return t('common.settings')
    default:
      return t('nav.appName')
  }
})
</script>

<template>
  <header class="app-header">
    <div class="header-left">
      <button class="menu-btn" @click="emit('toggleSidebar')" :title="t('common.toggleSidebar')">
        <i class="pi pi-bars"></i>
      </button>
      <h1 class="page-title">{{ pageTitle }}</h1>
    </div>
    <div class="header-right">
      <div class="connection-status" :class="{ connected: queryStore.isConnected }">
        <span class="status-dot"></span>
        <span class="status-text">{{ queryStore.isConnected ? t('common.connected') : t('common.disconnected') }}</span>
      </div>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  height: var(--header-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  border-bottom: 1px solid var(--color-border-light);
  flex-shrink: 0;
  background: var(--color-bg);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.menu-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  background: none;
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  transition: background var(--transition-fast);
}

.menu-btn:hover {
  background: var(--color-bg-tertiary);
}

.page-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.connection-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-error);
  transition: background var(--transition-fast);
}

.connection-status.connected .status-dot {
  background: var(--color-success);
}

.status-text {
  font-weight: 500;
}
</style>
