import { ref, watch } from 'vue'

export type Theme = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'app-theme'

function getSystemPreference(): 'light' | 'dark' {
  if (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark'
  }
  return 'light'
}

function getInitialTheme(): Theme {
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark' || stored === 'system') return stored
  }
  return 'system'
}

const currentTheme = ref<Theme>(getInitialTheme())

function applyTheme(theme: Theme) {
  const resolved = theme === 'system' ? getSystemPreference() : theme
  document.documentElement.setAttribute('data-theme', resolved)
}

// Apply on init
if (typeof window !== 'undefined') {
  applyTheme(currentTheme.value)

  // Listen for system theme changes
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (currentTheme.value === 'system') {
      applyTheme('system')
    }
  })
}

watch(currentTheme, (val) => {
  localStorage.setItem(STORAGE_KEY, val)
  applyTheme(val)
})

export function useTheme() {
  function setTheme(theme: Theme) {
    currentTheme.value = theme
  }

  return { theme: currentTheme, setTheme }
}
