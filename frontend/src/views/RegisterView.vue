<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'
import { useAuth } from '@/composables/useAuth'

const router = useRouter()
const { register, isLoading, error } = useAuth()

const name = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const validationErrors = ref<Record<string, string>>({})

const passwordStrength = computed(() => {
  const pwd = password.value
  if (!pwd) return 0
  let strength = 0
  if (pwd.length >= 6) strength++
  if (pwd.length >= 10) strength++
  if (/[A-Z]/.test(pwd)) strength++
  if (/[0-9]/.test(pwd)) strength++
  if (/[^A-Za-z0-9]/.test(pwd)) strength++
  return Math.min(strength, 4)
})

const passwordStrengthLabel = computed(() => {
  const labels = ['Very Weak', 'Weak', 'Fair', 'Strong', 'Very Strong']
  return labels[passwordStrength.value]
})

const passwordStrengthColor = computed(() => {
  const colors = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#10b981']
  return colors[passwordStrength.value]
})

const isFormValid = computed(() => {
  return name.value.trim() && 
         email.value.trim() && 
         password.value.length >= 6 &&
         password.value === confirmPassword.value
})

const validateForm = (): boolean => {
  const errors: Record<string, string> = {}

  if (!name.value.trim()) {
    errors.name = 'Full name is required'
  }

  if (!email.value.trim()) {
    errors.email = 'Email is required'
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)) {
    errors.email = 'Please enter a valid email address'
  }

  if (!password.value) {
    errors.password = 'Password is required'
  } else if (password.value.length < 6) {
    errors.password = 'Password must be at least 6 characters'
  }

  if (!confirmPassword.value) {
    errors.confirmPassword = 'Please confirm your password'
  } else if (password.value !== confirmPassword.value) {
    errors.confirmPassword = 'Passwords do not match'
  }

  validationErrors.value = errors
  return Object.keys(errors).length === 0
}

const clearError = () => {
  error.value = null
}

watch([name, email, password, confirmPassword], () => {
  validationErrors.value = {}
}, { deep: true })

const handleSubmit = async () => {
  clearError()

  if (!validateForm()) {
    return
  }

  const success = await register(email.value, password.value, name.value)
  
  if (success) {
    router.push('/chat')
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-background" />
    
    <div class="auth-container">
      <!-- Brand -->
      <div class="auth-brand">
        <div class="brand-icon">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <span class="brand-text">Prod Copilot</span>
      </div>

      <!-- Card -->
      <div class="auth-card">
        <div class="auth-header">
          <h1 class="auth-title">Create Account</h1>
          <p class="auth-subtitle">Get started for free</p>
        </div>

        <form class="auth-form" @submit.prevent="handleSubmit">
          <Message
            v-if="error"
            severity="error"
            :closable="true"
            @close="clearError"
            class="auth-error"
          >
            {{ error }}
          </Message>

          <div class="form-field">
            <label for="name" class="field-label">Full Name</label>
            <InputText
              id="name"
              v-model="name"
              type="text"
              placeholder="Enter your full name"
              class="field-input"
              :class="{ 'p-invalid': validationErrors.name }"
              :disabled="isLoading"
              autofocus
            />
            <small v-if="validationErrors.name" class="field-error">{{ validationErrors.name }}</small>
          </div>

          <div class="form-field">
            <label for="email" class="field-label">Email</label>
            <InputText
              id="email"
              v-model="email"
              type="email"
              placeholder="Enter your email"
              class="field-input"
              :class="{ 'p-invalid': validationErrors.email }"
              :disabled="isLoading"
            />
            <small v-if="validationErrors.email" class="field-error">{{ validationErrors.email }}</small>
          </div>

          <div class="form-field">
            <label for="password" class="field-label">Password</label>
            <Password
              id="password"
              v-model="password"
              placeholder="Create a password"
              class="field-input"
              :class="{ 'p-invalid': validationErrors.password }"
              :disabled="isLoading"
              toggleMask
              :feedback="false"
            />
            <small v-if="validationErrors.password" class="field-error">{{ validationErrors.password }}</small>
            
            <div v-if="password" class="password-strength">
              <div class="strength-bar">
                <div
                  class="strength-fill"
                  :style="{ 
                    width: `${(passwordStrength / 4) * 100}%`,
                    backgroundColor: passwordStrengthColor
                  }"
                />
              </div>
              <span class="strength-label" :style="{ color: passwordStrengthColor }">
                {{ passwordStrengthLabel }}
              </span>
            </div>
          </div>

          <div class="form-field">
            <label for="confirmPassword" class="field-label">Confirm Password</label>
            <Password
              id="confirmPassword"
              v-model="confirmPassword"
              placeholder="Confirm your password"
              class="field-input"
              :class="{ 'p-invalid': validationErrors.confirmPassword }"
              :disabled="isLoading"
              toggleMask
              :feedback="false"
              @keyup.enter="handleSubmit"
            />
            <small v-if="validationErrors.confirmPassword" class="field-error">{{ validationErrors.confirmPassword }}</small>
          </div>

          <Button
            type="submit"
            :loading="isLoading"
            :disabled="isLoading || !isFormValid"
            class="submit-button"
            label="Create Account"
          />
        </form>

        <div class="auth-footer">
          <span class="footer-text">Already have an account?</span>
          <router-link to="/login" class="footer-link">Sign in</router-link>
        </div>
      </div>

      <!-- Terms hint -->
      <p class="terms-hint">
        By creating an account, you agree to our Terms of Service and Privacy Policy
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  padding: 1rem;
  background-color: var(--color-bg, #ffffff);
}

/* Animated gradient background */
.auth-background {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 0;
  background: 
    radial-gradient(ellipse at 10% 20%, rgba(26, 115, 232, 0.12) 0%, transparent 50%),
    radial-gradient(ellipse at 90% 80%, rgba(26, 115, 232, 0.08) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 50%, rgba(26, 115, 232, 0.04) 0%, transparent 70%);
  animation: gradientShift 15s ease-in-out infinite;
}

@keyframes gradientShift {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.8; transform: scale(1.1); }
}

/* Container */
.auth-container {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 400px;
  animation: fadeInUp 0.5s ease-out;
}

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Brand */
.auth-brand {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.brand-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-accent, #1a73e8);
}

.brand-icon svg {
  width: 100%;
  height: 100%;
}

.brand-text {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-text-primary, #202124);
  letter-spacing: -0.02em;
}

/* Card */
.auth-card {
  background: var(--color-bg, #ffffff);
  border-radius: var(--radius-xl, 16px);
  border: 1px solid var(--color-border, #e0e0e0);
  box-shadow: var(--shadow-lg, 0 4px 20px rgba(0, 0, 0, 0.08));
  padding: 2rem;
  transition: all 0.3s ease;
}

.auth-header {
  text-align: center;
  margin-bottom: 1.5rem;
}

.auth-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--color-text-primary, #202124);
  margin: 0 0 0.25rem 0;
}

.auth-subtitle {
  font-size: 0.875rem;
  color: var(--color-text-secondary, #5f6368);
  margin: 0;
}

/* Form */
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.auth-error {
  margin: 0;
  border-radius: var(--radius-md, 8px);
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.field-label {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--color-text-primary, #202124);
}

.field-input {
  width: 100%;
}

.field-input :deep(.p-inputtext),
.field-input :deep(.p-password-input) {
  width: 100%;
  padding: 0.625rem 0.875rem;
  font-size: 0.9375rem;
  color: var(--color-text-primary, #202124);
  background: var(--color-bg, #ffffff);
  border: 1px solid var(--color-border, #e0e0e0);
  border-radius: var(--radius-md, 8px);
  transition: all 0.2s ease;
}

.field-input :deep(.p-inputtext:hover),
.field-input :deep(.p-password-input:hover) {
  border-color: var(--color-accent, #1a73e8);
}

.field-input :deep(.p-inputtext:focus),
.field-input :deep(.p-password-input:focus) {
  outline: none;
  border-color: var(--color-accent, #1a73e8);
  box-shadow: 0 0 0 3px rgba(26, 115, 232, 0.1);
}

.field-input :deep(.p-inputtext::placeholder),
.field-input :deep(.p-password-input::placeholder) {
  color: var(--color-text-tertiary, #80868b);
}

.field-input.p-invalid :deep(.p-inputtext),
.field-input.p-invalid :deep(.p-password-input) {
  border-color: var(--color-error, #ea4335);
}

.field-input.p-invalid :deep(.p-inputtext:focus),
.field-input.p-invalid :deep(.p-password-input:focus) {
  box-shadow: 0 0 0 3px rgba(234, 67, 53, 0.1);
}

.field-input :deep(.p-password-toggle) {
  color: var(--color-text-secondary, #5f6368);
  transition: color 0.2s ease;
}

.field-input :deep(.p-password-toggle:hover) {
  color: var(--color-text-primary, #202124);
}

.field-error {
  color: var(--color-error, #ea4335);
  font-size: 0.75rem;
  margin-top: 0.125rem;
}

/* Password strength */
.password-strength {
  margin-top: 0.375rem;
}

.strength-bar {
  height: 3px;
  background: var(--color-border-light, #eeeeee);
  border-radius: 2px;
  overflow: hidden;
}

.strength-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease, background-color 0.3s ease;
}

.strength-label {
  font-size: 0.6875rem;
  font-weight: 500;
  margin-top: 0.25rem;
  display: block;
  transition: color 0.3s ease;
}

/* Submit Button */
.submit-button {
  width: 100%;
  margin-top: 0.5rem;
  padding: 0.75rem 1rem;
  font-size: 0.9375rem;
  font-weight: 600;
  color: #ffffff;
  background: var(--color-accent, #1a73e8);
  border: none;
  border-radius: var(--radius-md, 8px);
  cursor: pointer;
  transition: all 0.2s ease;
}

.submit-button:hover:not(:disabled) {
  background: var(--color-accent-hover, #1557b0);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(26, 115, 232, 0.3);
}

.submit-button:active:not(:disabled) {
  transform: translateY(0);
}

.submit-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Footer */
.auth-footer {
  text-align: center;
  margin-top: 1.25rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--color-border-light, #eeeeee);
}

.footer-text {
  font-size: 0.875rem;
  color: var(--color-text-secondary, #5f6368);
}

.footer-link {
  font-size: 0.875rem;
  color: var(--color-accent, #1a73e8);
  text-decoration: none;
  font-weight: 500;
  margin-left: 0.25rem;
  transition: all 0.2s ease;
}

.footer-link:hover {
  text-decoration: underline;
}

/* Terms hint */
.terms-hint {
  text-align: center;
  margin-top: 1.25rem;
  font-size: 0.75rem;
  color: var(--color-text-tertiary, #80868b);
  line-height: 1.5;
  max-width: 280px;
  margin-left: auto;
  margin-right: auto;
}

/* Dark theme adjustments */
[data-theme="dark"] .auth-page {
  background-color: var(--color-bg, #1a1a1a);
}

[data-theme="dark"] .auth-background {
  background: 
    radial-gradient(ellipse at 10% 20%, rgba(138, 180, 248, 0.1) 0%, transparent 50%),
    radial-gradient(ellipse at 90% 80%, rgba(138, 180, 248, 0.06) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 50%, rgba(138, 180, 248, 0.03) 0%, transparent 70%);
}

[data-theme="dark"] .auth-card {
  background: var(--color-bg-secondary, #242424);
  border-color: var(--color-border, #3c4043);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

[data-theme="dark"] .brand-text {
  color: var(--color-text-primary, #e8eaed);
}

[data-theme="dark"] .auth-title {
  color: var(--color-text-primary, #e8eaed);
}

[data-theme="dark"] .auth-subtitle {
  color: var(--color-text-secondary, #9aa0a6);
}

[data-theme="dark"] .field-label {
  color: var(--color-text-primary, #e8eaed);
}

[data-theme="dark"] .field-input :deep(.p-inputtext),
[data-theme="dark"] .field-input :deep(.p-password-input) {
  background: var(--color-bg, #1a1a1a);
  border-color: var(--color-border, #3c4043);
  color: var(--color-text-primary, #e8eaed);
}

[data-theme="dark"] .field-input :deep(.p-inputtext::placeholder),
[data-theme="dark"] .field-input :deep(.p-password-input::placeholder) {
  color: var(--color-text-tertiary, #6b7280);
}

[data-theme="dark"] .field-input.p-invalid :deep(.p-inputtext),
[data-theme="dark"] .field-input.p-invalid :deep(.p-password-input) {
  border-color: var(--color-error, #f28b82);
}

[data-theme="dark"] .field-error {
  color: var(--color-error, #f28b82);
}

[data-theme="dark"] .strength-bar {
  background: var(--color-border, #3c4043);
}

[data-theme="dark"] .auth-footer {
  border-color: var(--color-border, #3c4043);
}

/* Responsive */
@media (max-width: 480px) {
  .auth-page {
    padding: 0.75rem;
  }
  
  .auth-card {
    padding: 1.5rem;
  }
  
  .auth-title {
    font-size: 1.375rem;
  }
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .auth-container,
  .auth-background {
    animation: none;
  }
  
  .auth-card,
  .submit-button,
  .field-input :deep(.p-inputtext),
  .strength-fill {
    transition: none;
  }
}
</style>
