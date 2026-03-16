<script setup lang="ts">
</script>

<template>
  <div class="dashboard-view">
    <div class="dashboard-container">
      <div class="dashboard-empty">
        <i class="pi pi-chart-bar empty-icon"></i>
        <h2 class="empty-title">Dashboard</h2>
        <p class="empty-description">
          Saved results and custom dashboards will appear here. Start by running queries in the Chat
          view and saving the results you want to track.
        </p>
        <router-link to="/chat" class="empty-action">
          Go to Chat
        </router-link>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-view {
  flex: 1;
  overflow-y: auto;
  padding: 32px;
}

.dashboard-container {
  max-width: 800px;
  margin: 0 auto;
}

.dashboard-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 80px 20px;
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  color: var(--color-border);
}

.empty-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.empty-description {
  font-size: 14px;
  color: var(--color-text-secondary);
  max-width: 420px;
  line-height: 1.6;
}

.empty-action {
  margin-top: 8px;
  padding: 10px 24px;
  background: var(--color-accent);
  color: white;
  border-radius: var(--radius-lg);
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: background var(--transition-fast);
}

.empty-action:hover {
  background: var(--color-accent-hover);
  text-decoration: none;
}
</style>
