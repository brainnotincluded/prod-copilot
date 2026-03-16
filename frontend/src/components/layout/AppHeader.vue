<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQueryStore } from '@/stores/query'
import { useLocale } from '@/composables/useLocale'
import { useAuth } from '@/composables/useAuth'
import Button from 'primevue/button'
import Menu from 'primevue/menu'
import type { MenuItem } from 'primevue/menuitem'

const props = defineProps<{
  sidebarCollapsed: boolean
}>()

const emit = defineEmits<{
  toggleSidebar: []
}>()

const route = useRoute()
const router = useRouter()
const queryStore = useQueryStore()
const { t } = useLocale()
const { user, role, isAdmin, logout } = useAuth()

const userMenuRef = ref<InstanceType<typeof Menu>>()

const roleBadgeClass = computed(() => {
  switch (role.value) {
    case 'admin': return 'role-admin'
    case 'editor': return 'role-editor'
    case 'viewer': return 'role-viewer'
    default: return ''
  }
})

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

const userMenuItems = computed<MenuItem[]>(() => [
  {
    label: user.value?.username || 'User',
    icon: 'pi pi-user',
    disabled: true,
  },
  {
    separator: true,
  },
  {
    label: 'Settings',
    icon: 'pi pi-cog',
    command: () => {
      if (route.path !== '/settings') {
        router.push('/settings')
      }
    },
  },
  {
    separator: true,
  },
  {
    label: 'Logout',
    icon: 'pi pi-sign-out',
    command: logout,
  },
])

const toggleUserMenu = (event: MouseEvent) => {
  userMenuRef.value?.toggle(event)
}
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
      <div class="role-badge" :class="roleBadgeClass" title="Current role">
        <i :class="isAdmin ? 'pi pi-shield' : 'pi pi-user'"></i>
        <span class="role-text">{{ role }}</span>
      </div>
      <div class="connection-status" :class="{ connected: queryStore.isConnected }">
        <span class="status-dot"></span>
        <span class="status-text">{{ queryStore.isConnected ? t('common.connected') : t('common.disconnected') }}</span>
      </div>
      
      <!-- User Menu -->
      <div class="user-menu-wrapper">
        <Button
          icon="pi pi-user-circle"
          class="user-menu-btn"
          text
          rounded
          :aria-label="'User menu'"
          @click="toggleUserMenu"
        />
        <Menu
          ref="userMenuRef"
          :model="userMenuItems"
          :popup="true"
          class="user-menu"
        />
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
  cursor: pointer;
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

.role-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--radius-md);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  background: var(--color-bg-tertiary);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border-light);
}

.role-badge.role-viewer {
  background: rgba(59, 130, 246, 0.1);
  color: var(--color-info);
  border-color: var(--color-info);
}

.role-badge.role-editor {
  background: rgba(34, 197, 94, 0.1);
  color: var(--color-success);
  border-color: var(--color-success);
}

.role-badge.role-admin {
  background: rgba(251, 188, 4, 0.1);
  color: var(--color-warning);
  border-color: var(--color-warning);
}

.role-badge i {
  font-size: 10px;
}

/* User Menu */
.user-menu-wrapper {
  position: relative;
}

.user-menu-btn {
  width: 36px;
  height: 36px;
  color: var(--color-text-secondary);
}

.user-menu-btn:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-primary);
}

/* Hide menu button on mobile - bottom nav is used instead */
@media (max-width: 768px) {
  .menu-btn {
    display: none;
  }
  
  .page-title {
    font-size: 18px;
    font-weight: 600;
  }
  
  .app-header {
    padding: 0 16px;
    height: var(--mobile-header-height);
  }
  
  .status-text {
    display: none;
  }
  
  .role-badge {
    display: none;
  }
}

@media (max-width: 640px) {
  .page-title {
    font-size: 17px;
  }
  
  .app-header {
    padding: 0 12px;
  }
}

/* Deep selectors for PrimeVue Menu styling */
:global(.user-menu.p-menu) {
  min-width: 160px;
}

:global(.user-menu .p-menu-item-disabled) {
  opacity: 1 !important;
}

:global(.user-menu .p-menu-item-disabled .p-menu-item-content) {
  font-weight: 600;
  color: var(--text-color) !important;
}
</style>
