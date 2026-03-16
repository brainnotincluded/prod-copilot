import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import 'primeicons/primeicons.css'

import App from './App.vue'
import router from './router'
import './style.css'
import '@/composables/useTheme'
import '@/composables/useLocale'
import { autoEnableMocks } from '@/composables/useMockApi'
import '@/mocks/setup'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(PrimeVue, {
  theme: {
    preset: Aura,
    options: {
      darkModeSelector: false,
      cssLayer: false,
    },
  },
})

app.mount('#app')

// Enable API mocks in test mode
autoEnableMocks()
