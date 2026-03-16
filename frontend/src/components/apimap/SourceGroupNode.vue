<script setup lang="ts">
defineProps<{
  data: {
    label: string
    endpointCount: number
  }
}>()
</script>

<template>
  <div class="source-group-label">
    <i class="pi pi-server source-icon"></i>
    <span class="source-name">{{ data.label }}</span>
    <span class="source-count">{{ data.endpointCount }} endpoints</span>
  </div>
</template>

<style scoped>
.source-group-label {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  pointer-events: none;
  user-select: none;
}

.source-icon {
  font-size: 14px;
  color: #6366f1;
}

.source-name {
  font-size: 14px;
  font-weight: 600;
  color: #3f3f46;
  letter-spacing: -0.01em;
}

.source-count {
  font-size: 11px;
  color: #a1a1aa;
  background: rgba(0, 0, 0, 0.04);
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

/* Mobile adaptations */
@media (max-width: 640px) {
  .source-group-label {
    padding: 12px 16px;
    gap: 10px;
  }

  .source-icon {
    font-size: 16px;
  }

  .source-name {
    font-size: 15px;
  }

  .source-count {
    font-size: 12px;
    padding: 3px 10px;
  }
}

@media (max-width: 480px) {
  .source-group-label {
    padding: 10px 12px;
    gap: 8px;
    flex-wrap: wrap;
  }

  .source-icon {
    font-size: 14px;
  }

  .source-name {
    font-size: 13px;
  }

  .source-count {
    font-size: 11px;
    padding: 2px 8px;
  }
}
</style>
