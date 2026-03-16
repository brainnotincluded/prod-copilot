<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

const props = defineProps<{
  data: Record<string, any>
  metadata?: Record<string, any>
}>()

const mapContainer = ref<HTMLElement | null>(null)
const mapReady = ref(false)

const title = computed(() => props.metadata?.title || '')

const markers = computed<Array<{ lat: number; lng: number; label?: string; popup?: string }>>(() => {
  if (Array.isArray(props.data.markers)) return props.data.markers
  if (Array.isArray(props.data.points)) return props.data.points
  if (Array.isArray(props.data)) {
    return props.data.filter(
      (item: any) =>
        item.lat !== undefined &&
        item.lng !== undefined
    )
  }
  return []
})

const center = computed<[number, number]>(() => {
  if (props.data.center) {
    return [props.data.center.lat, props.data.center.lng]
  }
  if (markers.value.length > 0) {
    const avgLat =
      markers.value.reduce((sum, m) => sum + m.lat, 0) / markers.value.length
    const avgLng =
      markers.value.reduce((sum, m) => sum + m.lng, 0) / markers.value.length
    return [avgLat, avgLng]
  }
  return [51.505, -0.09]
})

const zoom = computed(() => props.data.zoom || 10)

onMounted(async () => {
  if (!mapContainer.value) return

  const L = await import('leaflet')
  await import('leaflet/dist/leaflet.css')

  const map = L.map(mapContainer.value).setView(center.value, zoom.value)

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  }).addTo(map)

  const defaultIcon = L.icon({
    iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
    iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41],
  })

  markers.value.forEach((m) => {
    const marker = L.marker([m.lat, m.lng], { icon: defaultIcon }).addTo(map)
    if (m.popup || m.label) {
      marker.bindPopup(m.popup || m.label || '')
    }
  })

  if (markers.value.length > 1) {
    const bounds = L.latLngBounds(markers.value.map((m) => [m.lat, m.lng]))
    map.fitBounds(bounds, { padding: [40, 40] })
  }

  mapReady.value = true
})
</script>

<template>
  <div class="map-result result-fade-in">
    <div v-if="title" class="result-title">{{ title }}</div>
    <div ref="mapContainer" class="map-container"></div>
    <div v-if="markers.length > 0" class="map-info">
      {{ markers.length }} {{ markers.length === 1 ? 'локация' : 'локаций' }}
    </div>
  </div>
</template>

<style scoped>
.map-result {
  display: flex;
  flex-direction: column;
}

.result-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  padding: 12px 16px 0;
}

.map-container {
  height: 360px;
  width: 100%;
}

.map-info {
  padding: 8px 16px;
  font-size: 12px;
  color: var(--color-text-tertiary);
  border-top: 1px solid var(--color-border-light);
}
</style>
