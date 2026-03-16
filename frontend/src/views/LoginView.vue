<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'
import Card from 'primevue/card'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import Divider from 'primevue/divider'
import { useAuth } from '@/composables/useAuth'

const router = useRouter()
const route = useRoute()
const { login, register, isLoading, error } = useAuth()

// Active tab
const activeTab = ref('0')

// Login form
const loginEmail = ref('')
const loginPassword = ref('')

// Register form
const registerName = ref('')
const registerEmail = ref('')
const registerPassword = ref('')
const registerPasswordConfirm = ref('')
const registerErrors = ref<string[]>([])

const passwordsMatch = computed(() => 
  !registerPassword.value || 
  !registerPasswordConfirm.value || 
  registerPassword.value === registerPasswordConfirm.value
)

const canRegister = computed(() => 
  registerName.value.trim() &&
  registerEmail.value.trim() &&
  registerPassword.value.length >= 6 &&
  registerPassword.value === registerPasswordConfirm.value
)

const handleLogin = async () => {
  if (!loginEmail.value || !loginPassword.value) {
    return
  }

  const success = await login(loginEmail.value, loginPassword.value)
  
  if (success) {
    const redirectPath = route.query.redirect as string
    router.push(redirectPath || '/chat')
  }
}

const handleRegister = async () => {
  registerErrors.value = []
  
  // Validation
  if (!registerName.value.trim()) {
    registerErrors.value.push('Name is required')
  }
  if (!registerEmail.value.trim()) {
    registerErrors.value.push('Email is required')
  }
  if (registerPassword.value.length < 6) {
    registerErrors.value.push('Password must be at least 6 characters')
  }
  if (registerPassword.value !== registerPasswordConfirm.value) {
    registerErrors.value.push('Passwords do not match')
  }
  
  if (registerErrors.value.length > 0) {
    return
  }

  const success = await register(
    registerEmail.value,
    registerPassword.value,
    registerName.value
  )
  
  if (success) {
    const redirectPath = route.query.redirect as string
    router.push(redirectPath || '/chat')
  }
}

// Demo accounts
const demoAccounts = [
  { role: 'Admin', email: 'admin@example.com', password: 'admin123', color: '#ef4444' },
  { role: 'Editor', email: 'developer1@example.com', password: 'dev123', color: '#3b82f6' },
  { role: 'Viewer', email: 'viewer1@example.com', password: 'viewer123', color: '#10b981' },
]

const fillDemoAccount = (account: typeof demoAccounts[0]) => {
  loginEmail.value = account.email
  loginPassword.value = account.password
  activeTab.value = '0'
}
</script>

<template>
  <div class="login-page">
    <div class="login-container">
      <!-- Logo & Brand -->
      <div class="brand-section">
        <div class="logo">
          <i class="pi pi-shield"></i>
        </div>
        <h1 class="brand-title">Prod Copilot</h1>
        <p class="brand-subtitle">API Management & Orchestration Platform</p>
      </div>

      <Card class="login-card">
        <template #content>
          <Tabs v-model:value="activeTab" class="auth-tabs">
            <TabList>
              <Tab value="0">Sign In</Tab>
              <Tab value="1">Create Account</Tab>
            </TabList>

            <TabPanels>
              <!-- Login Tab -->
              <TabPanel value="0">
                <form @submit.prevent="handleLogin" class="auth-form">
                  <Message 
                    v-if="error" 
                    severity="error" 
                    :closable="false"
                    class="error-message"
                  >
                    {{ error }}
                  </Message>

                  <div class="field">
                    <label for="login-email">Email</label>
                    <InputText
                      id="login-email"
                      v-model="loginEmail"
                      type="email"
                      placeholder="Enter your email"
                      :disabled="isLoading"
                      autofocus
                      fluid
                      autocomplete="email"
                    />
                  </div>

                  <div class="field">
                    <label for="login-password">Password</label>
                    <Password
                      id="login-password"
                      v-model="loginPassword"
                      placeholder="Enter your password"
                      :feedback="false"
                      :disabled="isLoading"
                      toggleMask
                      fluid
                      autocomplete="current-password"
                      @keyup.enter="handleLogin"
                    />
                  </div>

                  <div class="form-options">
                    <div class="remember-me">
                      <!-- Optional: add remember me checkbox -->
                    </div>
                    <a href="#" class="forgot-password" @click.prevent>
                      Forgot password?
                    </a>
                  </div>

                  <Button
                    type="submit"
                    label="Sign In"
                    icon="pi pi-sign-in"
                    :loading="isLoading"
                    class="auth-button"
                    fluid
                  />
                </form>
              </TabPanel>

              <!-- Register Tab -->
              <TabPanel value="1">
                <form @submit.prevent="handleRegister" class="auth-form">
                  <Message 
                    v-if="error" 
                    severity="error" 
                    :closable="false"
                    class="error-message"
                  >
                    {{ error }}
                  </Message>

                  <Message 
                    v-for="(err, index) in registerErrors" 
                    :key="index"
                    severity="error" 
                    :closable="false"
                    class="error-message"
                  >
                    {{ err }}
                  </Message>

                  <div class="field">
                    <label for="register-name">Full Name</label>
                    <InputText
                      id="register-name"
                      v-model="registerName"
                      type="text"
                      placeholder="Enter your full name"
                      :disabled="isLoading"
                      fluid
                      autocomplete="name"
                    />
                  </div>

                  <div class="field">
                    <label for="register-email">Email</label>
                    <InputText
                      id="register-email"
                      v-model="registerEmail"
                      type="email"
                      placeholder="Enter your email"
                      :disabled="isLoading"
                      fluid
                      autocomplete="email"
                    />
                  </div>

                  <div class="field">
                    <label for="register-password">Password</label>
                    <Password
                      id="register-password"
                      v-model="registerPassword"
                      placeholder="Min 6 characters"
                      :disabled="isLoading"
                      toggleMask
                      fluid
                      autocomplete="new-password"
                    />
                  </div>

                  <div class="field">
                    <label for="register-password-confirm">Confirm Password</label>
                    <Password
                      id="register-password-confirm"
                      v-model="registerPasswordConfirm"
                      placeholder="Confirm your password"
                      :feedback="false"
                      :disabled="isLoading"
                      toggleMask
                      fluid
                      autocomplete="new-password"
                      :class="{ 'p-invalid': !passwordsMatch }"
                    />
                    <small v-if="!passwordsMatch" class="error-text">
                      Passwords do not match
                    </small>
                  </div>

                  <Button
                    type="submit"
                    label="Create Account"
                    icon="pi pi-user-plus"
                    :loading="isLoading"
                    :disabled="!canRegister"
                    class="auth-button"
                    fluid
                  />
                </form>
              </TabPanel>
            </TabPanels>
          </Tabs>

          <Divider align="center" type="solid">
            <span class="divider-text">Demo Accounts</span>
          </Divider>

          <!-- Demo Accounts -->
          <div class="demo-accounts">
            <button
              v-for="account in demoAccounts"
              :key="account.email"
              class="demo-account-btn"
              @click="fillDemoAccount(account)"
              :style="{ borderColor: account.color }"
            >
              <span class="demo-role" :style="{ backgroundColor: account.color }">
                {{ account.role }}
              </span>
              <span class="demo-email">{{ account.email }}</span>
            </button>
          </div>
        </template>
      </Card>

      <!-- Footer -->
      <p class="login-footer">
        <i class="pi pi-info-circle"></i>
        Demo environment — any data may be reset periodically
      </p>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--surface-ground) 0%, var(--surface-card) 100%);
  padding: 1rem;
}

.login-container {
  width: 100%;
  max-width: 440px;
}

/* Brand Section */
.brand-section {
  text-align: center;
  margin-bottom: 1.5rem;
}

.logo {
  width: 64px;
  height: 64px;
  margin: 0 auto 1rem;
  background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-600) 100%);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 14px rgba(var(--primary-rgb), 0.4);
}

.logo i {
  font-size: 2rem;
  color: white;
}

.brand-title {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text-color);
  margin: 0 0 0.25rem;
}

.brand-subtitle {
  font-size: 0.9rem;
  color: var(--text-color-secondary);
  margin: 0;
}

/* Card */
.login-card {
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08);
  border-radius: 16px;
}

.login-card :deep(.p-card-content) {
  padding: 0;
}

/* Tabs */
.auth-tabs :deep(.p-tablist) {
  border-bottom: 1px solid var(--surface-border);
}

.auth-tabs :deep(.p-tab) {
  flex: 1;
  justify-content: center;
  padding: 1rem;
  font-weight: 500;
}

.auth-tabs :deep(.p-tablist-content) {
  width: 100%;
}

/* Form */
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.5rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.field label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-color);
}

.error-message {
  margin-bottom: 0.5rem;
}

.error-text {
  color: var(--red-500);
  font-size: 0.75rem;
}

.form-options {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-top: -0.25rem;
}

.forgot-password {
  font-size: 0.875rem;
  color: var(--primary-color);
  text-decoration: none;
}

.forgot-password:hover {
  text-decoration: underline;
}

.auth-button {
  margin-top: 0.5rem;
  height: 2.75rem;
}

/* Divider */
:deep(.p-divider) {
  margin: 0;
}

.divider-text {
  font-size: 0.75rem;
  color: var(--text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Demo Accounts */
.demo-accounts {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 1rem 1.5rem 1.5rem;
}

.demo-account-btn {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.625rem 0.875rem;
  background: var(--surface-overlay);
  border: 1px solid var(--surface-border);
  border-left-width: 3px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
}

.demo-account-btn:hover {
  background: var(--surface-hover);
  transform: translateX(2px);
}

.demo-role {
  font-size: 0.625rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: white;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  white-space: nowrap;
}

.demo-email {
  font-size: 0.875rem;
  color: var(--text-color);
  font-family: monospace;
}

/* Footer */
.login-footer {
  text-align: center;
  margin-top: 1.5rem;
  font-size: 0.8rem;
  color: var(--text-color-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.login-footer i {
  font-size: 0.9rem;
}

/* Dark mode adjustments */
:deep(.p-card) {
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
}

:deep(.p-inputtext),
:deep(.p-password-input) {
  background: var(--surface-overlay);
}

/* Mobile optimizations */
@media (max-width: 480px) {
  .login-page {
    padding: 0.75rem;
    align-items: flex-start;
    padding-top: 5vh;
  }
  
  .brand-title {
    font-size: 1.5rem;
  }
  
  .logo {
    width: 56px;
    height: 56px;
  }
  
  .logo i {
    font-size: 1.75rem;
  }
  
  .auth-form {
    padding: 1rem;
  }
  
  .demo-accounts {
    padding: 1rem;
  }
  
  .demo-email {
    font-size: 0.75rem;
  }
}
</style>
