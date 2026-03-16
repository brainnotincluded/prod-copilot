<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useLocale } from '@/composables/useLocale'

const props = defineProps<{
  collapsed: boolean
  isMobile?: boolean
  mobileOpen?: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const route = useRoute()
const { t } = useLocale()

const navItems = computed(() => [
  { path: '/chat', label: t('nav.chat'), icon: 'pi pi-comment' },
  { path: '/swagger', label: t('nav.apiSources'), icon: 'pi pi-file' },
  { path: '/endpoints', label: t('nav.apiMaps'), icon: 'pi pi-sitemap' },
  { path: '/dashboard', label: t('nav.dashboard'), icon: 'pi pi-chart-bar' },
])

function isActive(path: string): boolean {
  return route.path === path
}

// Touch gesture handling for mobile swipe
let touchStartX = 0
let touchEndX = 0

function handleTouchStart(e: TouchEvent) {
  touchStartX = e.changedTouches[0].screenX
}

function handleTouchEnd(e: TouchEvent) {
  touchEndX = e.changedTouches[0].screenX
  handleSwipe()
}

function handleSwipe() {
  const swipeThreshold = 50
  const swipeDistance = touchEndX - touchStartX
  
  // Swipe right to open (from left edge)
  if (swipeDistance > swipeThreshold && touchStartX < 30 && props.isMobile && !props.mobileOpen) {
    // This should be handled by parent, emit event to open
    // We'll use a custom event or the parent can listen
  }
  
  // Swipe left to close
  if (swipeDistance < -swipeThreshold && props.mobileOpen) {
    emit('close')
  }
}

// Handle escape key to close mobile menu
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.mobileOpen) {
    emit('close')
  }
}

// Watch for mobile open state to handle body scroll lock
watch(() => props.mobileOpen, (isOpen) => {
  if (isOpen) {
    document.body.style.overflow = 'hidden'
  } else {
    document.body.style.overflow = ''
  }
})

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
  document.addEventListener('touchstart', handleTouchStart, { passive: true })
  document.addEventListener('touchend', handleTouchEnd, { passive: true })
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
  document.removeEventListener('touchstart', handleTouchStart)
  document.removeEventListener('touchend', handleTouchEnd)
  document.body.style.overflow = ''
})
</script>

<template>
  <aside 
    class="sidebar" 
    :class="{ 
      collapsed: collapsed && !isMobile, 
      'mobile-open': mobileOpen,
      'is-mobile': isMobile 
    }"
    role="navigation"
    aria-label="Main navigation"
  >
    <div class="sidebar-header">
      <div class="logo">
        <span class="logo-icon">P</span>
        <span v-if="!collapsed || isMobile" class="logo-text">{{ t('nav.appName') }}</span>
      </div>
      
      <!-- Mobile close button -->
      <button 
        v-if="isMobile" 
        class="mobile-close-btn hide-on-desktop"
        @click="$emit('close')"
        aria-label="Close menu"
      >
        <i class="pi pi-times"></i>
      </button>
    </div>

    <nav class="sidebar-nav">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-item touch-friendly"
        :class="{ active: isActive(item.path) }"
        :title="collapsed && !isMobile ? item.label : undefined"
        @click="isMobile && $emit('close')"
      >
        <i :class="item.icon" class="nav-icon"></i>
        <span v-if="!collapsed || isMobile" class="nav-label">{{ item.label }}</span>
      </router-link>
    </nav>

    <div class="sidebar-footer">
      <div 
        class="nav-item touch-friendly" 
        :title="collapsed && !isMobile ? t('common.settings') : undefined"
      >
        <i class="pi pi-cog nav-icon"></i>
        <span v-if="!collapsed || isMobile" class="nav-label">{{ t('common.settings') }}</span>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  width: var(--sidebar-width);
  background: var(--color-bg);
  border-right: 1px solid var(--color-border-light);
  display: flex;
  flex-direction: column;
  transition: width var(--transition-normal), transform var(--transition-normal);
  z-index: 1000;
  overflow: hidden;
}

.sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
}

.sidebar-header {
  height: var(--header-height);
  display: flex;
  align-items: center;
  padding: 0 12px;
  flex-shrink: 0;
  justify-content: space-between;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  overflow: hidden;
  white-space: nowrap;
}

.logo-icon {
  width: 32px;
  height: 32px;
  background: var(--color-accent);
  color: white;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 16px;
  flex-shrink: 0;
}

.logo-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.mobile-close-btn {
  display: none;
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  cursor: pointer;
  align-items: center;
  justify-content: center;
  transition: background var(--transition-fast);
}

.mobile-close-btn:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-primary);
}

.sidebar-nav {
  flex: 1;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
  overflow-x: hidden;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-lg);
  color: var(--color-text-secondary);
  text-decoration: none;
  transition: background var(--transition-fast), color var(--transition-fast);
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  flex-shrink: 0;
}

.nav-item:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-primary);
  text-decoration: none;
}

.nav-item.active {
  background: var(--color-accent-light);
  color: var(--color-accent);
}

.nav-icon {
  font-size: 18px;
  width: 20px;
  text-align: center;
  flex-shrink: 0;
}

.nav-label {
  font-size: 14px;
  font-weight: 500;
}

.sidebar-footer {
  padding: 8px;
  border-top: 1px solid var(--color-border-light);
  flex-shrink: 0;
}

/* ============================================
   MOBILE STYLES (<= 768px)
   ============================================ */

@media (max-width: 768px) {
  .sidebar {
    transform: translateX(-100%);
    width: var(--mobile-sidebar-width);
    z-index: 1001;
    box-shadow: var(--shadow-lg);
  }
  
  .sidebar.mobile-open {
    transform: translateX(0);
  }
  
  .sidebar-header {
    height: var(--mobile-header-height);
    padding: 0 16px;
    border-bottom: 1px solid var(--color-border-light);
  }
  
  .logo-text {
    font-size: 16px;
  }
  
  .mobile-close-btn {
    display: flex;
  }
  
  .sidebar-nav {
    padding: 12px;
    gap: 4px;
  }
  
  .nav-item {
    padding: 14px 16px;
    min-height: 48px;
  }
  
  .nav-icon {
    font-size: 20px;
    width: 24px;
  }
  
  .nav-label {
    font-size: 15px;
  }
  
  .sidebar-footer {
    padding: 12px;
  }
}

/* ============================================
   SMALL MOBILE (<= 480px)
   ============================================ */

@media (max-width: 480px) {
  .sidebar {
    width: var(--mobile-sidebar-width);
  }
  
  .sidebar-header {
    padding: 0 12px;
  }
  
  .sidebar-nav {
    padding: 8px;
  }
  
  .nav-item {
    padding: 12px 14px;
  }
}

/* ============================================
   TOUCH DEVICE OPTIMIZATIONS
   ============================================ */

@media (hover: none) and (pointer: coarse) {
  .nav-item {
    min-height: 44px;
  }
  
  .nav-item:hover {
    background: inherit;
    color: var(--color-text-secondary);
  }
  
  .nav-item:active {
    background: var(--color-bg-tertiary);
    opacity: 0.8;
  }
  
  .nav-item.active:hover {
    background: var(--color-accent-light);
    color: var(--color-accent);
  }
}
</style>
