<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useLocale } from '@/composables/useLocale'

const { t } = useLocale()

const props = defineProps<{
  data: Record<string, any>
  metadata?: Record<string, any>
}>()

const mapContainer = ref<HTMLElement | null>(null)
const mapReady = ref(false)
const mapInstance = ref<any>(null)
const LInstance = ref<any>(null)
const userLocationMarker = ref<any>(null)

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

// Detect mobile/tablet for responsive height
const isMobile = ref(false)
const isTablet = ref(false)
const isLocating = ref(false)
const locationError = ref('')

function updateBreakpoint() {
  const width = window.innerWidth
  isMobile.value = width <= 640
  isTablet.value = width > 640 && width <= 768
}

function getLocation() {
  if (!navigator.geolocation) {
    locationError.value = t('results.geolocationNotSupported')
    return
  }

  isLocating.value = true
  locationError.value = ''

  navigator.geolocation.getCurrentPosition(
    (position) => {
      const { latitude, longitude } = position.coords
      isLocating.value = false

      if (mapInstance.value && LInstance.value) {
        // Remove existing user location marker
        if (userLocationMarker.value) {
          mapInstance.value.removeLayer(userLocationMarker.value)
        }

        // Add user location marker with different color
        const userIcon = LInstance.value.divIcon({
          className: 'user-location-marker',
          html: '<div class="user-location-dot"></div>',
          iconSize: [20, 20],
          iconAnchor: [10, 10],
        })

        userLocationMarker.value = LInstance.value.marker([latitude, longitude], { icon: userIcon })
          .addTo(mapInstance.value)
          .bindPopup(t('results.yourLocation'))

        // Pan to user location
        mapInstance.value.setView([latitude, longitude], 15)
      }
    },
    (error) => {
      isLocating.value = false
      switch (error.code) {
        case error.PERMISSION_DENIED:
          locationError.value = t('results.locationPermissionDenied')
          break
        case error.POSITION_UNAVAILABLE:
          locationError.value = t('results.locationUnavailable')
          break
        case error.TIMEOUT:
          locationError.value = t('results.locationTimeout')
          break
        default:
          locationError.value = t('results.locationError')
      }
    },
    {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 60000,
    }
  )
}

onMounted(async () => {
  updateBreakpoint()
  window.addEventListener('resize', updateBreakpoint)

  if (!mapContainer.value) return

  const L = await import('leaflet')
  await import('leaflet/dist/leaflet.css')

  LInstance.value = L

  // Create map with touch support
  const map = L.map(mapContainer.value, {
    center: center.value,
    zoom: zoom.value,
    // Enable touch interactions
    touchZoom: true,
    scrollWheelZoom: true,
    doubleClickZoom: true,
    boxZoom: true,
    keyboard: true,
    dragging: true,
  })

  mapInstance.value = map

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  }).addTo(map)

  // Larger touch-friendly icon for mobile
  const iconSize: [number, number] = isMobile.value ? [30, 46] : [25, 41]
  const iconAnchor: [number, number] = isMobile.value ? [15, 46] : [12, 41]
  const popupAnchor: [number, number] = isMobile.value ? [1, -40] : [1, -34]
  const shadowSize: [number, number] = isMobile.value ? [46, 46] : [41, 41]

  const defaultIcon = L.icon({
    iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
    iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
    iconSize,
    iconAnchor,
    popupAnchor,
    shadowSize,
  })

  markers.value.forEach((m) => {
    const marker = L.marker([m.lat, m.lng], { icon: defaultIcon }).addTo(map)
    if (m.popup || m.label) {
      marker.bindPopup(m.popup || m.label || '')
    }
  })

  if (markers.value.length > 1) {
    const bounds = L.latLngBounds(markers.value.map((m) => [m.lat, m.lng]))
    map.fitBounds(bounds, { padding: isMobile.value ? [20, 20] : [40, 40] })
  }

  mapReady.value = true
})
</script>

<template>
  <div class="map-result result-fade-in">
    <div v-if="title" class="result-title">{{ title }}</div>
    <div class="map-wrapper">
      <div ref="mapContainer" class="map-container" :class="{ 'map-mobile': isMobile, 'map-tablet': isTablet }"></div>
      <!-- Location button -->
      <button
        class="location-btn"
        :class="{ 'locating': isLocating }"
        @click="getLocation"
        :title="t('results.myLocation')"
        :disabled="isLocating"
      >
        <i class="pi" :class="isLocating ? 'pi-spin pi-spinner' : 'pi-crosshairs'"></i>
      </button>
    </div>
    <div v-if="locationError" class="location-error">
      {{ locationError }}
    </div>
    <div v-if="markers.length > 0" class="map-info">
      {{ t('results.locations', markers.length) }}
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

.map-wrapper {
  position: relative;
  width: 100%;
}

.map-container {
  height: 400px;
  width: 100%;
}

/* Tablet map height */
.map-container.map-tablet {
  height: 320px;
}

/* Mobile map height */
.map-container.map-mobile {
  height: 280px;
}

/* Location button */
.location-btn {
  position: absolute;
  bottom: 20px;
  right: 20px;
  z-index: 1000;
  background: white;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
  transition: all var(--transition-fast);
  color: var(--color-text-secondary);
}

.location-btn:hover {
  background: var(--color-bg-secondary);
  color: var(--color-accent);
  border-color: var(--color-accent);
}

.location-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.location-btn.locating {
  color: var(--color-accent);
}

.location-error {
  padding: 8px 16px;
  font-size: 12px;
  color: var(--color-error, #ea4335);
  background: var(--color-error-bg, rgba(234, 67, 53, 0.1));
  border-top: 1px solid var(--color-border-light);
}

.map-info {
  padding: 8px 16px;
  font-size: 12px;
  color: var(--color-text-tertiary);
  border-top: 1px solid var(--color-border-light);
}

/* Tablet styles */
@media (max-width: 768px) {
  .map-container {
    height: 320px;
  }

  .result-title {
    font-size: 13px;
    padding: 10px 14px 0;
  }

  .map-info {
    padding: 8px 14px;
    font-size: 12px;
  }

  .location-error {
    padding: 8px 14px;
    font-size: 12px;
  }

  .location-btn {
    bottom: 16px;
    right: 16px;
  }
}

/* Mobile styles (< 640px) */
@media (max-width: 640px) {
  .map-container {
    height: 280px;
  }

  .result-title {
    font-size: 13px;
    padding: 10px 12px 0;
  }

  .map-info {
    padding: 6px 12px;
    font-size: 11px;
  }

  .location-error {
    padding: 6px 12px;
    font-size: 11px;
  }

  .location-btn {
    bottom: 70px;
    right: 12px;
    width: 44px;
    height: 44px;
  }

  /* Touch-friendly controls - larger tap targets */
  .map-container :deep(.leaflet-control-zoom a) {
    width: 44px;
    height: 44px;
    line-height: 44px;
    font-size: 20px;
  }

  .map-container :deep(.leaflet-control-attribution) {
    font-size: 10px;
    max-width: 50%;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

/* User location marker styles */
:deep(.user-location-marker) {
  background: transparent;
}

:deep(.user-location-dot) {
  width: 16px;
  height: 16px;
  background: var(--color-accent, #1a73e8);
  border: 3px solid white;
  border-radius: 50%;
  box-shadow: 0 0 0 2px var(--color-accent, #1a73e8);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 2px var(--color-accent, #1a73e8), 0 0 0 4px rgba(26, 115, 232, 0.3);
  }
  50% {
    box-shadow: 0 0 0 2px var(--color-accent, #1a73e8), 0 0 0 8px rgba(26, 115, 232, 0);
  }
  100% {
    box-shadow: 0 0 0 2px var(--color-accent, #1a73e8), 0 0 0 4px rgba(26, 115, 232, 0);
  }
}
</style>
