<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import Toast from '@/components/ui/Toast.vue'
import BottomNav from '@/components/layout/BottomNav.vue'

const route = useRoute()
const sidebarCollapsed = ref(false)
const isMobile = ref(false)
const mobileMenuOpen = ref(false)

// Hide sidebar and header on public pages (login/register)
const isPublicPage = computed(() => route.meta.public === true)

function checkMobile() {
  isMobile.value = window.innerWidth <= 768
  if (!isMobile.value) {
    mobileMenuOpen.value = false
  }
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})

function toggleMobileMenu() {
  mobileMenuOpen.value = !mobileMenuOpen.value
}

function closeMobileMenu() {
  mobileMenuOpen.value = false
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}
</script>

<template>
  <div class="app-layout" :class="{ 'public-page': isPublicPage }">
    <!-- Mobile Overlay -->
    <div 
      v-if="!isPublicPage"
      class="mobile-overlay" 
      :class="{ active: isMobile && mobileMenuOpen }"
      @click="closeMobileMenu"
      aria-hidden="true"
    ></div>
    
    <AppSidebar 
      v-if="!isPublicPage"
      :collapsed="sidebarCollapsed" 
      :is-mobile="isMobile"
      :mobile-open="mobileMenuOpen"
      @close="closeMobileMenu"
    />
    
    <div class="app-main" :class="{ 
      'sidebar-collapsed': sidebarCollapsed && !isMobile && !isPublicPage,
      'is-mobile': isMobile,
      'no-sidebar': isPublicPage
    }">
      <AppHeader 
        v-if="!isPublicPage"
        @toggle-sidebar="isMobile ? toggleMobileMenu() : toggleSidebar()" 
        :sidebar-collapsed="sidebarCollapsed"
        :is-mobile="isMobile"
      />
      <main class="app-content" :class="{ 'auth-content': isPublicPage }">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
    
    <!-- Bottom Navigation for Mobile -->
    <BottomNav v-if="isMobile && !isPublicPage" />
    
    <Toast />
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  height: 100dvh; /* Dynamic viewport height for mobile */
  width: 100%;
  overflow: hidden;
}

.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin-left: var(--sidebar-width);
  transition: margin-left var(--transition-normal);
  min-width: 0;
  overflow: hidden;
}

.app-main.sidebar-collapsed {
  margin-left: var(--sidebar-collapsed-width);
}

.app-main.no-sidebar {
  margin-left: 0;
}

.app-content.auth-content {
  padding: 0;
  overflow: auto;
}

.app-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: relative;
}

/* Mobile Overlay */
.mobile-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  opacity: 0;
  visibility: hidden;
  transition: opacity var(--transition-normal), visibility var(--transition-normal);
  backdrop-filter: blur(2px);
}

.mobile-overlay.active {
  opacity: 1;
  visibility: visible;
}

/* ============================================
   TABLET (<= 1024px)
   ============================================ */

@media (max-width: 1024px) {
  .app-main {
    margin-left: var(--sidebar-width);
  }
}

/* ============================================
   MOBILE (<= 768px)
   ============================================ */

@media (max-width: 768px) {
  .app-layout {
    flex-direction: column;
  }
  
  .app-main {
    margin-left: 0 !important;
    width: 100%;
    height: 100%;
  }
  
  .app-content {
    /* Padding for bottom navigation */
    padding-bottom: calc(var(--mobile-nav-height) + var(--safe-area-bottom));
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
  }
  
  /* Ensure overlay is above everything except sidebar */
  .mobile-overlay {
    z-index: 1000;
  }
}

/* ============================================
   MOBILE PORTRAIT (<= 640px)
   ============================================ */

@media (max-width: 640px) {
  .app-content {
    /* Slightly more padding for smaller screens */
    padding-bottom: calc(var(--mobile-nav-height) + var(--safe-area-bottom) + 8px);
  }
}

/* ============================================
   SMALL MOBILE (<= 480px)
   ============================================ */

@media (max-width: 480px) {
  .app-main {
    min-width: 320px; /* Minimum readable width */
  }
  
  .app-content {
    padding-bottom: calc(var(--mobile-nav-height) + var(--safe-area-bottom));
  }
}

/* ============================================
   SAFE AREA SUPPORT (Notch Devices)
   ============================================ */

@supports (padding-top: env(safe-area-inset-top)) {
  @media (max-width: 768px) {
    .app-content {
      padding-top: env(safe-area-inset-top);
    }
  }
}
</style>
