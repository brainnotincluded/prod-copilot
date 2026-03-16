<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useSwaggerStore } from '@/stores/swagger'
import { useToast } from '@/composables/useToast'
import { useLocale } from '@/composables/useLocale'
import type { SwaggerUploadResult } from '@/types'

const swaggerStore = useSwaggerStore()
const { showToast } = useToast()
const router = useRouter()
const { t } = useLocale()

const activeTab = ref<'file' | 'url'>('file')
const isDragging = ref(false)
const isTouchDragging = ref(false)
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
    { label: mode === 'url' ? t('swagger.fetchingSpec') : t('swagger.readingFile'), status: 'active' },
    { label: t('swagger.parsingEndpoints'), status: 'pending' },
    { label: t('swagger.generatingEmbeddings'), status: 'pending' },
    { label: t('swagger.indexingRag'), status: 'pending' },
    { label: t('swagger.done'), status: 'pending' },
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
  last.detail = t('swagger.endpointsIndexed', result.endpoints_count)
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

// Touch events for mobile drag & drop indication
function handleTouchStart(event: TouchEvent) {
  isTouchDragging.value = true
}

function handleTouchEnd(event: TouchEvent) {
  isTouchDragging.value = false
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
    uploadError.value = t('swagger.invalidFile')
    showToast(t('swagger.invalidFile'), 'error')
    return
  }

  resetProgress()
  isUploading.value = true
  initProgressSteps('file')

  try {
    setTimeout(() => {
      if (isUploading.value) advanceProgress(1)
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

    showToast(t('swagger.importSuccess', result.name, result.endpoints_count), 'success')
  } catch {
    uploadError.value = swaggerStore.error || t('swagger.uploadFailed')
    progressSteps.value = []
    showToast(swaggerStore.error || t('swagger.uploadFailed'), 'error')
  } finally {
    isUploading.value = false
  }
}

// --- URL Import ---
async function importFromUrl() {
  const url = importUrl.value.trim()
  if (!url) {
    uploadError.value = t('swagger.enterUrl')
    return
  }

  try {
    new URL(url)
  } catch {
    uploadError.value = t('swagger.invalidUrl')
    showToast(t('swagger.invalidUrl'), 'error')
    return
  }

  resetProgress()
  isUploading.value = true
  initProgressSteps('url')

  try {
    setTimeout(() => {
      if (isUploading.value) advanceProgress(1)
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

    showToast(t('swagger.importSuccess', result.name, result.endpoints_count), 'success')

    importUrl.value = ''
    importName.value = ''
  } catch {
    uploadError.value = swaggerStore.error || t('swagger.importFailed')
    progressSteps.value = []
    showToast(swaggerStore.error || t('swagger.importFailed'), 'error')
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
        <span class="tab-text">{{ t('swagger.fileUpload') }}</span>
      </button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'url' }"
        @click="activeTab = 'url'; resetProgress()"
      >
        <i class="pi pi-link"></i>
        <span class="tab-text">{{ t('swagger.urlImport') }}</span>
      </button>
    </div>

    <!-- File Upload Tab -->
    <div v-if="activeTab === 'file'" class="tab-content">
      <div
        class="upload-zone"
        :class="{
          dragging: isDragging,
          'touch-dragging': isTouchDragging,
          uploading: isUploading,
        }"
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
        @drop="handleDrop"
        @click="triggerFileInput"
        @touchstart="handleTouchStart"
        @touchend="handleTouchEnd"
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
          <p class="upload-text">{{ t('swagger.dropZone') }}</p>
          <p class="upload-hint">{{ t('swagger.formats') }}</p>
        </div>
      </div>
    </div>

    <!-- URL Import Tab -->
    <div v-if="activeTab === 'url'" class="tab-content">
      <div class="url-form">
        <div class="form-field">
          <label class="form-label" for="swagger-url">{{ t('swagger.specUrl') }}</label>
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
            {{ t('swagger.apiName') }}
            <span class="form-label-hint">{{ t('swagger.optional') }}</span>
          </label>
          <input
            id="swagger-name"
            v-model="importName"
            type="text"
            class="form-input"
            placeholder="My API"
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
          {{ isUploading ? t('swagger.importing') : t('swagger.import') }}
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
          <span class="result-count">{{ t('swagger.endpointsIndexed', uploadResult.endpoints_count) }}</span>
          <span v-if="uploadResult.base_url" class="result-base-url">
            {{ uploadResult.base_url }}
          </span>
        </div>
      </div>
      <div class="result-actions">
        <button class="result-btn primary" @click="goToApiMaps">
          <i class="pi pi-map"></i>
          {{ t('swagger.viewApiMaps') }}
        </button>
        <button class="result-btn secondary" @click="dismissResult">
          {{ t('swagger.dismiss') }}
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
  min-height: 48px;
  min-width: 44px;
  touch-action: manipulation;
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

.tab-btn:active {
  transform: scale(0.98);
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
  padding: 40px 24px;
  text-align: center;
  cursor: pointer;
  transition: border-color var(--transition-fast), background var(--transition-fast);
  min-height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  touch-action: manipulation;
}

.upload-zone:hover,
.upload-zone.dragging,
.upload-zone.touch-dragging {
  border-color: var(--color-accent);
  background: var(--color-accent-light);
}

.upload-zone.uploading {
  opacity: 0.7;
  pointer-events: none;
}

.upload-zone:active {
  transform: scale(0.99);
}

.file-input {
  display: none;
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.upload-icon {
  font-size: 32px;
  color: var(--color-text-tertiary);
}

.upload-zone:hover .upload-icon,
.upload-zone.dragging .upload-icon,
.upload-zone.touch-dragging .upload-icon {
  color: var(--color-accent);
}

.upload-text {
  font-size: 15px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.upload-hint {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

/* URL Form */
.url-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
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
  padding: 12px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 14px;
  color: var(--color-text-primary);
  background: var(--color-bg);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  outline: none;
  width: 100%;
  box-sizing: border-box;
  min-height: 48px;
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
  gap: 8px;
  padding: 14px 24px;
  background: var(--color-accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition-fast), transform 0.1s ease;
  min-height: 48px;
  touch-action: manipulation;
}

.import-btn:hover:not(:disabled) {
  background: var(--color-accent-hover);
}

.import-btn:active:not(:disabled) {
  transform: scale(0.98);
}

.import-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Error */
.upload-error {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  font-size: 14px;
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
  padding: 10px;
  font-size: 12px;
  min-width: 44px;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  touch-action: manipulation;
  border-radius: var(--radius-sm);
}

.error-dismiss:hover {
  opacity: 1;
  background: rgba(0, 0, 0, 0.05);
}

/* Progress Stepper */
.progress-stepper {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 16px 18px;
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
  padding: 18px;
  background: #f0faf3;
  border: 1px solid #c3e6cb;
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.result-icon {
  font-size: 22px;
  color: var(--color-success);
  flex-shrink: 0;
  margin-top: 1px;
}

.result-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.result-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.result-count {
  font-size: 14px;
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
  gap: 10px;
}

.result-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px 18px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: background var(--transition-fast), transform 0.1s ease;
  min-height: 48px;
  touch-action: manipulation;
}

.result-btn:active {
  transform: scale(0.98);
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

/* Tablet (< 768px) */
@media (max-width: 768px) {
  .swagger-upload {
    gap: 10px;
  }

  .tab-btn {
    padding: 12px 14px;
    min-height: 48px;
  }

  .upload-zone {
    padding: 32px 20px;
    min-height: 150px;
  }

  .upload-icon {
    font-size: 28px;
  }

  .url-form {
    gap: 14px;
  }

  .progress-stepper {
    padding: 14px 16px;
  }
}

/* Tablet (641px - 1024px) */
@media (min-width: 641px) and (max-width: 1024px) {
  .upload-zone {
    min-height: 180px;
    padding: 48px 32px;
  }

  .upload-icon {
    font-size: 36px;
  }

  .url-form {
    gap: 18px;
  }
}

/* Mobile (max-width: 640px) */
@media (max-width: 640px) {
  .swagger-upload {
    gap: 10px;
  }

  .tab-toggle {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    border-radius: var(--radius-md);
  }

  .tab-toggle::-webkit-scrollbar {
    display: none;
  }

  .tab-btn {
    flex-shrink: 0;
    padding: 12px 16px;
    min-width: 120px;
    min-height: 48px;
    font-size: 13px;
  }

  .tab-btn i {
    font-size: 15px;
  }

  .tab-text {
    white-space: nowrap;
  }

  /* Drag & drop зона - адаптивная высота */
  .upload-zone {
    padding: 24px 16px;
    min-height: 120px;
    border-radius: var(--radius-md);
  }

  .upload-icon {
    font-size: 24px;
  }

  .upload-text {
    font-size: 14px;
  }

  .upload-hint {
    font-size: 12px;
  }

  .upload-content {
    gap: 8px;
  }

  .url-form {
    gap: 12px;
  }

  .form-field {
    gap: 4px;
  }

  .form-label {
    font-size: 11px;
  }

  /* Input поля - 100% ширины на мобильных */
  .form-input {
    font-size: 16px; /* Prevent zoom on iOS */
    padding: 12px 12px;
    min-height: 48px;
  }

  .import-btn {
    padding: 14px 20px;
    font-size: 15px;
    min-height: 52px;
    width: 100%;
  }

  /* Кнопки - full width stack на мобильных */
  .result-actions {
    flex-direction: column;
    gap: 8px;
  }

  .result-btn {
    width: 100%;
    min-height: 52px;
    font-size: 15px;
    padding: 14px 18px;
  }

  .upload-error {
    padding: 12px 14px;
    font-size: 13px;
  }

  .error-dismiss {
    min-width: 44px;
    min-height: 44px;
  }

  .progress-stepper {
    padding: 12px 14px;
  }

  .step-label {
    font-size: 13px;
  }

  .upload-result {
    padding: 14px;
    gap: 14px;
  }

  .result-icon {
    font-size: 20px;
  }

  .result-name {
    font-size: 14px;
  }
}

/* Small mobile (max-width: 375px) */
@media (max-width: 375px) {
  .upload-zone {
    padding: 20px 12px;
    min-height: 100px;
  }

  .upload-icon {
    font-size: 22px;
  }

  .upload-text {
    font-size: 13px;
  }

  .upload-hint {
    font-size: 11px;
  }

  .tab-btn {
    min-width: 100px;
    padding: 10px 12px;
    min-height: 44px;
    font-size: 12px;
  }

  .tab-btn i {
    font-size: 14px;
  }

  .form-input {
    padding: 10px 12px;
    font-size: 16px;
    min-height: 44px;
  }

  .import-btn {
    min-height: 48px;
    padding: 12px 16px;
    font-size: 14px;
  }

  .result-btn {
    min-height: 48px;
    font-size: 14px;
    padding: 12px 16px;
  }

  .step-label {
    font-size: 12px;
  }

  .progress-stepper {
    padding: 10px 12px;
  }
}
</style>
