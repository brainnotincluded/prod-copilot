<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useSwaggerStore } from '@/stores/swagger'
import { useToast } from '@/composables/useToast'
import type { SwaggerUploadResult } from '@/types'

const swaggerStore = useSwaggerStore()
const { showToast } = useToast()
const router = useRouter()

const activeTab = ref<'file' | 'url'>('file')
const isDragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

// URL import fields
const importUrl = ref('')
const importName = ref('')

// Progress state
type ProgressStep = {
  label: string
  status: 'pending' | 'active' | 'done'
  detail?: string
}

const isUploading = ref(false)
const uploadError = ref('')
const uploadResult = ref<SwaggerUploadResult | null>(null)
const progressSteps = ref<ProgressStep[]>([])

const showProgress = computed(() => progressSteps.value.length > 0)

function resetProgress() {
  progressSteps.value = []
  uploadError.value = ''
  uploadResult.value = null
}

function initProgressSteps(mode: 'file' | 'url') {
  progressSteps.value = [
    { label: mode === 'url' ? 'Загрузка спецификации...' : 'Чтение файла...', status: 'active' },
    { label: 'Парсинг эндпоинтов...', status: 'pending' },
    { label: 'Генерация эмбеддингов...', status: 'pending' },
    { label: 'Индексация в RAG...', status: 'pending' },
    { label: 'Готово!', status: 'pending' },
  ]
}

function advanceProgress(stepIndex: number, detail?: string) {
  for (let i = 0; i < progressSteps.value.length; i++) {
    if (i < stepIndex) {
      progressSteps.value[i].status = 'done'
    } else if (i === stepIndex) {
      progressSteps.value[i].status = 'active'
      if (detail) progressSteps.value[i].detail = detail
    } else {
      progressSteps.value[i].status = 'pending'
    }
  }
}

function completeProgress(result: SwaggerUploadResult) {
  for (let i = 0; i < progressSteps.value.length - 1; i++) {
    progressSteps.value[i].status = 'done'
  }
  const last = progressSteps.value[progressSteps.value.length - 1]
  last.status = 'done'
  last.detail = `${result.endpoints_count} эндпоинтов проиндексировано`
}

// --- File Upload ---
function handleDragOver(event: DragEvent) {
  event.preventDefault()
  isDragging.value = true
}

function handleDragLeave() {
  isDragging.value = false
}

function handleDrop(event: DragEvent) {
  event.preventDefault()
  isDragging.value = false
  const files = event.dataTransfer?.files
  if (files && files.length > 0) {
    uploadFile(files[0])
  }
}

function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    uploadFile(target.files[0])
    target.value = ''
  }
}

function triggerFileInput() {
  if (isUploading.value) return
  fileInput.value?.click()
}

async function uploadFile(file: File) {
  const validExtensions = ['.json', '.yaml', '.yml']
  const ext = '.' + file.name.split('.').pop()?.toLowerCase()

  if (!validExtensions.includes(ext)) {
    uploadError.value = 'Пожалуйста, загрузите файл JSON или YAML.'
    showToast('Пожалуйста, загрузите файл JSON или YAML.', 'error')
    return
  }

  resetProgress()
  isUploading.value = true
  initProgressSteps('file')

  try {
    // Simulate progress steps while waiting for response
    setTimeout(() => {
      if (isUploading.value) advanceProgress(1, 'Анализ спецификации...')
    }, 800)
    setTimeout(() => {
      if (isUploading.value) advanceProgress(2)
    }, 2000)
    setTimeout(() => {
      if (isUploading.value) advanceProgress(3)
    }, 3500)

    const result = await swaggerStore.uploadSwagger(file)
    uploadResult.value = result
    completeProgress(result)

    showToast(
      `Успешно импортировано ${result.name} -- ${result.endpoints_count} эндпоинтов проиндексировано`,
      'success',
    )
  } catch {
    uploadError.value = swaggerStore.error || 'Загрузка не удалась. Попробуйте снова.'
    progressSteps.value = []
    showToast(swaggerStore.error || 'Загрузка не удалась. Попробуйте снова.', 'error')
  } finally {
    isUploading.value = false
  }
}

// --- URL Import ---
async function importFromUrl() {
  const url = importUrl.value.trim()
  if (!url) {
    uploadError.value = 'Пожалуйста, введите URL.'
    return
  }

  try {
    new URL(url)
  } catch {
    uploadError.value = 'Пожалуйста, введите корректный URL.'
    showToast('Пожалуйста, введите корректный URL.', 'error')
    return
  }

  resetProgress()
  isUploading.value = true
  initProgressSteps('url')

  try {
    setTimeout(() => {
      if (isUploading.value) advanceProgress(1, 'Парсинг спецификации...')
    }, 1200)
    setTimeout(() => {
      if (isUploading.value) advanceProgress(2)
    }, 2500)
    setTimeout(() => {
      if (isUploading.value) advanceProgress(3)
    }, 4000)

    const name = importName.value.trim() || undefined
    const result = await swaggerStore.uploadSwaggerFromUrl(url, name)
    uploadResult.value = result
    completeProgress(result)

    showToast(
      `Успешно импортировано ${result.name} -- ${result.endpoints_count} эндпоинтов проиндексировано`,
      'success',
    )

    importUrl.value = ''
    importName.value = ''
  } catch {
    uploadError.value = swaggerStore.error || 'Импорт не удался. Проверьте URL и попробуйте снова.'
    progressSteps.value = []
    showToast(
      swaggerStore.error || 'Импорт не удался. Проверьте URL и попробуйте снова.',
      'error',
    )
  } finally {
    isUploading.value = false
  }
}

function goToApiMaps() {
  router.push('/endpoints')
}

function dismissResult() {
  resetProgress()
}
</script>

<template>
  <div class="swagger-upload">
    <!-- Tab Toggle -->
    <div class="tab-toggle">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'file' }"
        @click="activeTab = 'file'; resetProgress()"
      >
        <i class="pi pi-upload"></i>
        Загрузка файла
      </button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'url' }"
        @click="activeTab = 'url'; resetProgress()"
      >
        <i class="pi pi-link"></i>
        Импорт по URL
      </button>
    </div>

    <!-- File Upload Tab -->
    <div v-if="activeTab === 'file'" class="tab-content">
      <div
        class="upload-zone"
        :class="{
          dragging: isDragging,
          uploading: isUploading,
        }"
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
        @drop="handleDrop"
        @click="triggerFileInput"
      >
        <input
          ref="fileInput"
          type="file"
          accept=".json,.yaml,.yml"
          class="file-input"
          @change="handleFileSelect"
        />

        <div class="upload-content">
          <i class="pi pi-cloud-upload upload-icon"></i>
          <p class="upload-text">
            Перетащите файл Swagger/OpenAPI сюда или нажмите для выбора
          </p>
          <p class="upload-hint">Поддерживаются форматы JSON и YAML</p>
        </div>
      </div>
    </div>

    <!-- URL Import Tab -->
    <div v-if="activeTab === 'url'" class="tab-content">
      <div class="url-form">
        <div class="form-field">
          <label class="form-label" for="swagger-url">URL спецификации</label>
          <input
            id="swagger-url"
            v-model="importUrl"
            type="url"
            class="form-input"
            placeholder="https://api.example.com/openapi.json"
            :disabled="isUploading"
            @keyup.enter="importFromUrl"
          />
        </div>
        <div class="form-field">
          <label class="form-label" for="swagger-name">
            Название API
            <span class="form-label-hint">(необязательно)</span>
          </label>
          <input
            id="swagger-name"
            v-model="importName"
            type="text"
            class="form-input"
            placeholder="Мой API"
            :disabled="isUploading"
            @keyup.enter="importFromUrl"
          />
        </div>
        <button
          class="import-btn"
          :disabled="isUploading || !importUrl.trim()"
          @click="importFromUrl"
        >
          <i class="pi" :class="isUploading ? 'pi-spin pi-spinner' : 'pi-download'"></i>
          {{ isUploading ? 'Импортирую...' : 'Импортировать' }}
        </button>
      </div>
    </div>

    <!-- Error message -->
    <div v-if="uploadError && !showProgress" class="upload-error">
      <i class="pi pi-exclamation-circle"></i>
      <span>{{ uploadError }}</span>
      <button class="error-dismiss" @click="uploadError = ''">
        <i class="pi pi-times"></i>
      </button>
    </div>

    <!-- Progress Stepper -->
    <div v-if="showProgress" class="progress-stepper">
      <div
        v-for="(step, idx) in progressSteps"
        :key="idx"
        class="progress-step"
        :class="step.status"
      >
        <div class="step-indicator">
          <i
            v-if="step.status === 'done'"
            class="pi pi-check step-icon done"
          ></i>
          <i
            v-else-if="step.status === 'active'"
            class="pi pi-spin pi-spinner step-icon active"
          ></i>
          <span v-else class="step-dot"></span>
        </div>
        <div class="step-content">
          <span class="step-label">{{ step.label }}</span>
          <span v-if="step.detail" class="step-detail">{{ step.detail }}</span>
        </div>
      </div>
    </div>

    <!-- Success Result -->
    <div v-if="uploadResult && !isUploading" class="upload-result">
      <div class="result-header">
        <i class="pi pi-check-circle result-icon"></i>
        <div class="result-info">
          <span class="result-name">{{ uploadResult.name }}</span>
          <span class="result-count">{{ uploadResult.endpoints_count }} эндпоинтов проиндексировано</span>
          <span v-if="uploadResult.base_url" class="result-base-url">
            {{ uploadResult.base_url }}
          </span>
        </div>
      </div>
      <div class="result-actions">
        <button class="result-btn primary" @click="goToApiMaps">
          <i class="pi pi-map"></i>
          Открыть на Карте API
        </button>
        <button class="result-btn secondary" @click="dismissResult">
          Закрыть
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.swagger-upload {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Tab Toggle */
.tab-toggle {
  display: flex;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--color-bg-secondary);
}

.tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 16px;
  border: none;
  background: none;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tab-btn:first-child {
  border-right: 1px solid var(--color-border-light);
}

.tab-btn.active {
  background: var(--color-bg);
  color: var(--color-accent);
  font-weight: 600;
}

.tab-btn:hover:not(.active) {
  color: var(--color-text-primary);
}

.tab-btn i {
  font-size: 14px;
}

.tab-content {
  animation: tabFadeIn 0.2s ease;
}

@keyframes tabFadeIn {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* File Upload Zone */
.upload-zone {
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-lg);
  padding: 36px 20px;
  text-align: center;
  cursor: pointer;
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.upload-zone:hover,
.upload-zone.dragging {
  border-color: var(--color-accent);
  background: var(--color-accent-light);
}

.upload-zone.uploading {
  opacity: 0.7;
  pointer-events: none;
}

.file-input {
  display: none;
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.upload-icon {
  font-size: 28px;
  color: var(--color-text-tertiary);
}

.upload-zone:hover .upload-icon,
.upload-zone.dragging .upload-icon {
  color: var(--color-accent);
}

.upload-text {
  font-size: 14px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.upload-hint {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

/* URL Form */
.url-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.form-label-hint {
  font-weight: 400;
  text-transform: none;
  color: var(--color-text-tertiary);
  letter-spacing: 0;
}

.form-input {
  padding: 9px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--color-text-primary);
  background: var(--color-bg);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  outline: none;
}

.form-input::placeholder {
  color: var(--color-text-tertiary);
}

.form-input:focus {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px rgba(26, 115, 232, 0.12);
}

.form-input:disabled {
  background: var(--color-bg-secondary);
  cursor: not-allowed;
}

.import-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 20px;
  background: var(--color-accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.import-btn:hover:not(:disabled) {
  background: var(--color-accent-hover);
}

.import-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Error */
.upload-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  background: #fde7e7;
  color: var(--color-error);
  border: 1px solid #f5c6cb;
}

.error-dismiss {
  margin-left: auto;
  background: none;
  border: none;
  color: inherit;
  opacity: 0.6;
  cursor: pointer;
  padding: 0;
  font-size: 12px;
}

.error-dismiss:hover {
  opacity: 1;
}

/* Progress Stepper */
.progress-stepper {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 14px 16px;
  background: var(--color-bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-light);
}

.progress-step {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 6px 0;
  position: relative;
}

.progress-step:not(:last-child)::after {
  content: '';
  position: absolute;
  left: 8px;
  top: 24px;
  bottom: -6px;
  width: 1px;
  background: var(--color-border);
}

.progress-step.done:not(:last-child)::after {
  background: var(--color-success);
}

.step-indicator {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
}

.step-icon {
  font-size: 14px;
}

.step-icon.done {
  color: var(--color-success);
}

.step-icon.active {
  color: var(--color-accent);
}

.step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-border);
}

.step-content {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.step-label {
  font-size: 13px;
  color: var(--color-text-tertiary);
  font-weight: 400;
}

.progress-step.active .step-label {
  color: var(--color-text-primary);
  font-weight: 500;
}

.progress-step.done .step-label {
  color: var(--color-text-secondary);
}

.step-detail {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

/* Success Result */
.upload-result {
  padding: 16px;
  background: #f0faf3;
  border: 1px solid #c3e6cb;
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.result-header {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.result-icon {
  font-size: 20px;
  color: var(--color-success);
  flex-shrink: 0;
  margin-top: 1px;
}

.result-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.result-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.result-count {
  font-size: 13px;
  color: var(--color-success);
  font-weight: 500;
}

.result-base-url {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--color-text-tertiary);
}

.result-actions {
  display: flex;
  gap: 8px;
}

.result-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 14px;
  border-radius: var(--radius-md);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: background var(--transition-fast);
}

.result-btn.primary {
  background: var(--color-accent);
  color: white;
}

.result-btn.primary:hover {
  background: var(--color-accent-hover);
}

.result-btn.secondary {
  background: transparent;
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
}

.result-btn.secondary:hover {
  background: var(--color-bg-secondary);
}

@media (max-width: 640px) {
  .upload-zone {
    padding: 28px 16px;
  }

  .result-actions {
    flex-direction: column;
  }
}
</style>
