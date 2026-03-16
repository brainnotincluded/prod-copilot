<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Select from 'primevue/select'
import Message from 'primevue/message'
import Card from 'primevue/card'
import { useAuth, type UserRole } from '@/composables/useAuth'

const router = useRouter()
const route = useRoute()
const { login, isLoading, error } = useAuth()

const username = ref('')
const password = ref('')
const selectedRole = ref<UserRole>('editor')

const roleOptions = [
  { label: 'Viewer (read-only)', value: 'viewer' as UserRole },
  { label: 'Editor (upload & chat)', value: 'editor' as UserRole },
  { label: 'Admin (full access)', value: 'admin' as UserRole },
]

const handleLogin = async () => {
  const success = await login(username.value, password.value, selectedRole.value)
  
  if (success) {
    // Redirect to originally requested page or default to chat
    const redirectPath = route.query.redirect as string
    router.push(redirectPath || '/chat')
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-container">
      <Card class="login-card">
        <template #title>
          <div class="login-header">
            <i class="pi pi-shield logo-icon"></i>
            <h1>Welcome Back</h1>
            <p>Sign in to access Prod Copilot</p>
          </div>
        </template>

        <template #content>
          <form @submit.prevent="handleLogin" class="login-form">
            <Message 
              v-if="error" 
              severity="error" 
              :closable="false"
              class="error-message"
            >
              {{ error }}
            </Message>

            <div class="field">
              <label for="username">Username</label>
              <InputText
                id="username"
                v-model="username"
                type="text"
                placeholder="Enter your username"
                :disabled="isLoading"
                autofocus
                fluid
              />
            </div>

            <div class="field">
              <label for="password">Password</label>
              <Password
                id="password"
                v-model="password"
                placeholder="Enter your password"
                :feedback="false"
                :disabled="isLoading"
                toggleMask
                fluid
              />
            </div>

            <div class="field">
              <label for="role">Role</label>
              <Select
                id="role"
                v-model="selectedRole"
                :options="roleOptions"
                optionLabel="label"
                optionValue="value"
                :disabled="isLoading"
                fluid
              />
            </div>

            <Button
              type="submit"
              label="Sign In"
              icon="pi pi-sign-in"
              :loading="isLoading"
              class="login-button"
              fluid
            />
          </form>
        </template>

        <template #footer>
          <div class="login-footer">
            <p class="hint">
              <i class="pi pi-info-circle"></i>
              Any password with 3+ characters works for demo
            </p>
          </div>
        </template>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-ground);
  padding: 1rem;
}

.login-container {
  width: 100%;
  max-width: 420px;
}

.login-card {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

.login-header {
  text-align: center;
  padding: 0.5rem 0 1rem;
}

.logo-icon {
  font-size: 3rem;
  color: var(--primary-color);
  margin-bottom: 1rem;
}

.login-header h1 {
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-color);
  margin: 0 0 0.5rem;
}

.login-header p {
  color: var(--text-color-secondary);
  margin: 0;
  font-size: 0.95rem;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.field label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-color);
}

.error-message {
  margin-bottom: 0.5rem;
}

.login-button {
  margin-top: 0.5rem;
}

.login-footer {
  text-align: center;
  padding-top: 0.5rem;
}

.hint {
  font-size: 0.8rem;
  color: var(--text-color-secondary);
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.hint i {
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

:deep(.p-select) {
  background: var(--surface-overlay);
}

/* Mobile optimizations */
@media (max-width: 480px) {
  .login-page {
    padding: 0.75rem;
    align-items: flex-start;
    padding-top: 10vh;
  }
  
  .login-header h1 {
    font-size: 1.5rem;
  }
  
  .logo-icon {
    font-size: 2.5rem;
  }
}
</style>
