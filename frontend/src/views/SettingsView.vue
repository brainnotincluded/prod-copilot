<script setup lang="ts">
import { useLocale, type Locale } from '@/composables/useLocale'
import { useTheme, type Theme } from '@/composables/useTheme'
import { useAuth, type UserRole } from '@/composables/useAuth'

const { locale, t } = useLocale()
const { theme, setTheme } = useTheme()
const { role, setRole, canUpload, canDelete } = useAuth()

const roles: { value: UserRole; label: string; icon: string; desc: string }[] = [
  { value: 'viewer', label: 'Viewer', icon: 'pi pi-eye', desc: 'Read-only access' },
  { value: 'editor', label: 'Editor', icon: 'pi pi-pencil', desc: 'Upload & query APIs' },
  { value: 'admin', label: 'Admin', icon: 'pi pi-shield', desc: 'Full access' },
]

const languages: { value: Locale; label: string; flag: string }[] = [
  { value: 'ru', label: 'Русский', flag: '🇷🇺' },
  { value: 'en', label: 'English', flag: '🇺🇸' },
]

const themes: { value: Theme; icon: string; key: string }[] = [
  { value: 'light', icon: 'pi pi-sun', key: 'settings.themeLight' },
  { value: 'dark', icon: 'pi pi-moon', key: 'settings.themeDark' },
  { value: 'system', icon: 'pi pi-desktop', key: 'settings.themeSystem' },
]

function selectLocale(loc: Locale) {
  locale.value = loc
}
</script>

<template>
  <div class="settings-view">
    <div class="settings-container">
      <h1 class="settings-title">{{ t('common.settings') }}</h1>

      <!-- Language -->
      <section class="settings-section">
        <h2 class="section-title">{{ t('settings.language') }}</h2>
        <p class="section-desc">{{ t('settings.languageDesc') }}</p>
        <div class="option-cards">
          <button
            v-for="lang in languages"
            :key="lang.value"
            class="option-card"
            :class="{ active: locale === lang.value }"
            @click="selectLocale(lang.value)"
          >
            <span class="option-flag">{{ lang.flag }}</span>
            <span class="option-label">{{ lang.label }}</span>
            <i v-if="locale === lang.value" class="pi pi-check option-check"></i>
          </button>
        </div>
      </section>

      <!-- Theme -->
      <section class="settings-section">
        <h2 class="section-title">{{ t('settings.theme') }}</h2>
        <p class="section-desc">{{ t('settings.themeDesc') }}</p>
        <div class="option-cards three">
          <button
            v-for="th in themes"
            :key="th.value"
            class="option-card"
            :class="{ active: theme === th.value }"
            @click="setTheme(th.value)"
          >
            <i :class="th.icon" class="option-icon"></i>
            <span class="option-label">{{ t(th.key) }}</span>
            <i v-if="theme === th.value" class="pi pi-check option-check"></i>
          </button>
        </div>
      </section>

      <!-- Dev Mode: User Role -->
      <section class="settings-section dev-section">
        <h2 class="section-title">{{ t('settings.devRole') }}</h2>
        <p class="section-desc">{{ t('settings.devRoleDesc') }}</p>
        <div class="option-cards three">
          <button
            v-for="r in roles"
            :key="r.value"
            class="option-card"
            :class="{ active: role === r.value }"
            @click="setRole(r.value)"
          >
            <i :class="r.icon" class="option-icon"></i>
            <div class="role-info">
              <span class="option-label">{{ r.label }}</span>
              <span class="role-desc">{{ r.desc }}</span>
            </div>
            <i v-if="role === r.value" class="pi pi-check option-check"></i>
          </button>
        </div>
        <div class="role-permissions">
          <div class="permission-item" :class="{ allowed: canUpload }">
            <i :class="canUpload ? 'pi pi-check' : 'pi pi-times'"></i>
            <span>{{ t('settings.canUpload') }}</span>
          </div>
          <div class="permission-item" :class="{ allowed: canDelete }">
            <i :class="canDelete ? 'pi pi-check' : 'pi pi-times'"></i>
            <span>{{ t('settings.canDelete') }}</span>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.settings-view {
  flex: 1;
  overflow-y: auto;
  padding: 32px 20px;
}

.settings-container {
  max-width: 600px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.settings-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text-primary);
  letter-spacing: -0.3px;
}

.settings-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.section-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.5;
}

.option-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.option-cards.three {
  grid-template-columns: 1fr 1fr 1fr;
}

.option-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border: 1.5px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  background: var(--color-bg);
  cursor: pointer;
  transition: border-color var(--transition-fast), background var(--transition-fast), box-shadow var(--transition-fast);
  position: relative;
}

.option-card:hover {
  border-color: var(--color-border);
  box-shadow: var(--shadow-sm);
}

.option-card.active {
  border-color: var(--color-accent);
  background: var(--color-accent-light);
}

.option-flag {
  font-size: 20px;
  line-height: 1;
}

.option-icon {
  font-size: 18px;
  color: var(--color-text-secondary);
}

.option-card.active .option-icon {
  color: var(--color-accent);
}

.option-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  flex: 1;
}

.option-check {
  font-size: 12px;
  color: var(--color-accent);
  font-weight: 700;
}

.role-info {
  display: flex;
  flex-direction: column;
  flex: 1;
  gap: 2px;
}

.role-desc {
  font-size: 11px;
  color: var(--color-text-secondary);
}

.dev-section {
  border-top: 1px dashed var(--color-border);
  padding-top: 24px;
}

.role-permissions {
  display: flex;
  gap: 20px;
  margin-top: 8px;
  padding: 12px 16px;
  background: var(--color-bg-elevated);
  border-radius: var(--radius-lg);
}

.permission-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.permission-item i {
  font-size: 12px;
  color: var(--color-text-muted);
}

.permission-item.allowed i {
  color: var(--color-success);
}

.permission-item.allowed {
  color: var(--color-text-primary);
}

@media (max-width: 480px) {
  .option-cards,
  .option-cards.three {
    grid-template-columns: 1fr;
  }
  
  .role-permissions {
    flex-direction: column;
    gap: 8px;
  }
}
</style>
