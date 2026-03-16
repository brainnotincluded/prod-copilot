<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  data: Record<string, any>
  metadata?: Record<string, any>
}>()

const images = computed(() => {
  if (props.data.images && Array.isArray(props.data.images)) {
    return props.data.images
  }
  if (props.data.url) {
    return [{ url: props.data.url, title: props.data.title || '' }]
  }
  return []
})

const title = computed(() => props.data.title || props.metadata?.title || '')
</script>

<template>
  <div class="image-result">
    <div v-if="title && images.length <= 1" class="image-title">{{ title }}</div>
    <div class="image-grid" :class="{ single: images.length === 1 }">
      <figure v-for="(img, idx) in images" :key="idx" class="image-item">
        <a :href="img.url" target="_blank" rel="noopener">
          <img :src="img.url" :alt="img.title || 'Generated image'" loading="lazy" />
        </a>
        <figcaption v-if="img.title && images.length > 1">{{ img.title }}</figcaption>
      </figure>
    </div>
  </div>
</template>

<style scoped>
.image-result {
  padding: 16px;
}

.image-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 12px;
}

.image-grid {
  display: grid;
  gap: 12px;
}

.image-grid.single {
  grid-template-columns: 1fr;
}

.image-grid:not(.single) {
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
}

.image-item {
  margin: 0;
}

.image-item img {
  width: 100%;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: opacity 0.2s;
}

.image-item img:hover {
  opacity: 0.9;
}

figcaption {
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
  text-align: center;
}
</style>
