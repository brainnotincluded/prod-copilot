<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useLocale } from '@/composables/useLocale'

const route = useRoute()
const router = useRouter()
const { t } = useLocale()

const navItems = computed(() => [
  { path: '/chat', label: t('nav.chat'), icon: 'pi pi-comment' },
  { path: '/swagger', label: t('nav.apiSources'), icon: 'pi pi-file' },
  { path: '/endpoints', label: t('nav.apiMaps'), icon: 'pi pi-sitemap' },
  { path: '/scenarios', label: t('nav.scenarios'), icon: 'pi pi-share-alt' },
  { path: '/dashboard', label: t('nav.dashboard'), icon: 'pi pi-chart-bar' },
])

function isActive(path: string): boolean {
  return route.path === path
}

function navigate(path: string) {
  router.push(path)
}
</script>

<template>
  <nav class="bottom-nav">
    <button
      v-for="item in navItems"
      :key="item.path"
      class="nav-item"
      :class="{ active: isActive(item.path) }"
      @click="navigate(item.path)"
    >
      <i :class="item.icon" class="nav-icon"></i>
      <span class="nav-label">{{ item.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: calc(var(--mobile-nav-height) + var(--safe-area-bottom, 0px));
  background: var(--color-bg);
  border-top: 1px solid var(--color-border-light);
  display: flex;
  align-items: flex-start;
  justify-content: space-around;
  padding-top: 6px;
  padding-bottom: var(--safe-area-bottom, 0px);
  z-index: 100;
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05);
}

.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 4px 12px;
  border: none;
  background: none;
  color: var(--color-text-tertiary);
  font-size: 10px;
  cursor: pointer;
  transition: color var(--transition-fast);
  min-width: 56px;
  min-height: 44px;
  touch-action: manipulation;
  flex: 1;
  max-width: 80px;
}

.nav-item:active {
  transform: scale(0.95);
}

.nav-item.active {
  color: var(--color-accent);
}

.nav-icon {
  font-size: 20px;
  margin-bottom: 2px;
}

.nav-label {
  font-size: 10px;
  font-weight: 500;
  white-space: nowrap;
}

/* Small mobile adjustments */
@media (max-width: 375px) {
  .nav-item {
    padding: 4px 8px;
    min-width: 48px;
  }
  
  .nav-icon {
    font-size: 18px;
  }
  
  .nav-label {
    font-size: 9px;
  }
}

/* Landscape mode on small devices */
@media (max-height: 500px) and (max-width: 768px) {
  .bottom-nav {
    height: 56px;
    padding-top: 4px;
  }
  
  .nav-item {
    flex-direction: row;
    gap: 6px;
    min-height: 36px;
  }
  
  .nav-icon {
    font-size: 16px;
    margin-bottom: 0;
  }
  
  .nav-label {
    font-size: 12px;
  }
}
</style>
