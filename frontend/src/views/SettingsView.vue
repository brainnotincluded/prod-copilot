<script setup lang="ts">
import { useLocale, type Locale } from '@/composables/useLocale'
import { useTheme, type Theme } from '@/composables/useTheme'

const { locale, t } = useLocale()
const { theme, setTheme } = useTheme()

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

@media (max-width: 480px) {
  .option-cards,
  .option-cards.three {
    grid-template-columns: 1fr;
  }
}
</style>
