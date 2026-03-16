import { ref, computed } from 'vue'
import en from '@/locales/en'
import ru from '@/locales/ru'

export type Locale = 'en' | 'ru'

const STORAGE_KEY = 'app-locale'

function getInitialLocale(): Locale {
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'en' || stored === 'ru') return stored
    const browserLang = navigator.language.slice(0, 2)
    if (browserLang === 'ru') return 'ru'
  }
  return 'en'
}

const currentLocale = ref<Locale>(getInitialLocale())

const messages: Record<Locale, Record<string, string>> = { en, ru }

export function useLocale() {
  const locale = computed({
    get: () => currentLocale.value,
    set: (val: Locale) => {
      currentLocale.value = val
      localStorage.setItem(STORAGE_KEY, val)
    },
  })

  function t(key: string, ...args: (string | number)[]): string {
    const msg = messages[currentLocale.value][key] ?? messages.en[key] ?? key
    if (args.length === 0) return msg
    return msg.replace(/\{(\d+)\}/g, (_, i) => String(args[Number(i)] ?? ''))
  }

  function toggleLocale() {
    locale.value = currentLocale.value === 'en' ? 'ru' : 'en'
  }

  return { locale, t, toggleLocale }
}
