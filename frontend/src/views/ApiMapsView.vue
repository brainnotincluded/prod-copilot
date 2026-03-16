<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { VueFlow, useVueFlow, Position } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'
import { useEndpointsStore } from '@/stores/endpoints'
import { useSwaggerStore } from '@/stores/swagger'
import SourceGroupNode from '@/components/apimap/SourceGroupNode.vue'
import EndpointNode from '@/components/apimap/EndpointNode.vue'
import type { EndpointItem } from '@/types'

const endpointsStore = useEndpointsStore()
const swaggerStore = useSwaggerStore()
const { fitView } = useVueFlow()

interface SelectedEndpoint extends EndpointItem {
  color: string
}

const selectedEndpoint = ref<SelectedEndpoint | null>(null)

const METHOD_COLORS: Record<string, string> = {
  GET: '#34a853',
  POST: '#1a73e8',
  PUT: '#f59e0b',
  DELETE: '#ea4335',
  PATCH: '#673ab7',
  HEAD: '#607d8b',
  OPTIONS: '#795548',
}

const METHOD_ORDER: Record<string, number> = {
  GET: 0,
  POST: 1,
  PUT: 2,
  PATCH: 3,
  DELETE: 4,
  HEAD: 5,
  OPTIONS: 6,
}

function getSourceName(sourceId: number): string {
  const source = swaggerStore.swaggers.find((s) => s.id === sourceId)
  return source?.name || `API Source ${sourceId}`
}

// ---------------------------------------------------------------------------
// Resource extraction helpers
// ---------------------------------------------------------------------------

/** Extract the terminal resource name from a path.
 *  /users           -> "users"
 *  /users/{id}      -> "users"
 *  /posts/{id}/comments -> "comments"
 *  /albums/{id}/photos  -> "photos"
 */
function extractResource(path: string): string {
  const parts = path.split('/').filter(Boolean)
  const nonParam = parts.filter((p) => !p.startsWith('{'))
  return nonParam[nonParam.length - 1] || path
}

/** Determine if this endpoint is a "detail" route (has trailing {param}). */
function isDetailRoute(path: string): boolean {
  const parts = path.split('/').filter(Boolean)
  return parts.length > 0 && parts[parts.length - 1].startsWith('{')
}

/** Get parent resource path for nested resources.
 *  /posts/{id}/comments -> "/posts"
 *  /users/{id}          -> null (not nested)
 */
function getParentResourcePath(path: string): string | null {
  const match = path.match(/^(\/[^/]+)\/\{[^}]+\}\/([^/]+)/)
  return match ? match[1] : null
}

/** Detect FK references from parameter names.
 *  "userId" -> "users", "postId" -> "posts"
 */
function detectFKFromParam(paramName: string): string | null {
  const fkMatch = paramName.match(/^(.+?)Id$/i)
  if (!fkMatch) return null
  // userId -> users (pluralise naively)
  const base = fkMatch[1].toLowerCase()
  return base + 's'
}

// ---------------------------------------------------------------------------
// Layout constants
// ---------------------------------------------------------------------------

const ENDPOINT_NODE_W = 240
const ENDPOINT_NODE_H = 58
const CLUSTER_GAP_X = 80 // gap between collection/detail columns
const CLUSTER_GAP_Y = 14 // vertical gap between endpoint cards
const RESOURCE_CLUSTER_GAP_X = 420 // wide horizontal gap so FK arrows don't cross nodes
const RESOURCE_CLUSTER_GAP_Y = 280 // tall vertical gap for the same reason
const GROUP_PADDING_X = 50
const GROUP_PADDING_Y = 70 // top padding for group label
const GROUP_PADDING_BOTTOM = 50

// ---------------------------------------------------------------------------
// Build graph
// ---------------------------------------------------------------------------

const graphElements = computed(() => {
  const nodes: any[] = []
  const edges: any[] = []

  // Group endpoints by source
  const bySource: Record<string, EndpointItem[]> = {}
  for (const ep of endpointsStore.endpoints) {
    const sourceId = String(ep.swagger_source_id)
    if (!bySource[sourceId]) bySource[sourceId] = []
    bySource[sourceId].push(ep)
  }

  let globalSourceOffsetY = 0

  for (const [sourceId, eps] of Object.entries(bySource)) {
    const sourceName = getSourceName(Number(sourceId))
    const groupNodeId = `group-${sourceId}`

    // --- Build resource clusters ---
    const resourceMap = new Map<string, EndpointItem[]>()
    for (const ep of eps) {
      const res = extractResource(ep.path)
      if (!resourceMap.has(res)) resourceMap.set(res, [])
      resourceMap.get(res)!.push(ep)
    }

    // Sort endpoints within each resource by method order then path length
    for (const [, resEps] of resourceMap) {
      resEps.sort((a, b) => {
        const ma = METHOD_ORDER[a.method] ?? 99
        const mb = METHOD_ORDER[b.method] ?? 99
        if (ma !== mb) return ma - mb
        return a.path.length - b.path.length
      })
    }

    // Determine connectivity: which resources reference which via FK or nesting
    const resourceNames = Array.from(resourceMap.keys())
    const incomingFKCount = new Map<string, number>()
    for (const r of resourceNames) incomingFKCount.set(r, 0)

    for (const [, resEps] of resourceMap) {
      for (const ep of resEps) {
        // FK from parameters
        for (const param of ep.parameters || []) {
          const fkTarget = detectFKFromParam(param.name || '')
          if (fkTarget && resourceMap.has(fkTarget)) {
            incomingFKCount.set(fkTarget, (incomingFKCount.get(fkTarget) || 0) + 1)
          }
        }
      }
    }

    // Sort resources: most referenced first (center), then alphabetical
    const sortedResources = resourceNames.slice().sort((a, b) => {
      const ca = incomingFKCount.get(a) || 0
      const cb = incomingFKCount.get(b) || 0
      if (cb !== ca) return cb - ca
      return a.localeCompare(b)
    })

    // Layout resource clusters in a grid pattern
    const COLS = Math.max(1, Math.min(4, Math.ceil(Math.sqrt(sortedResources.length))))

    // Pre-calculate each cluster's size for accurate group sizing
    interface ClusterLayout {
      resource: string
      endpoints: EndpointItem[]
      x: number
      y: number
      width: number
      height: number
    }
    const clusterLayouts: ClusterLayout[] = []

    let maxGroupW = 0
    let maxGroupH = 0

    for (let idx = 0; idx < sortedResources.length; idx++) {
      const resource = sortedResources[idx]
      const resEps = resourceMap.get(resource)!
      const col = idx % COLS
      const row = Math.floor(idx / COLS)

      // Inside a cluster: list endpoints (GET list) on left, detail (GET {id}) right,
      // mutations below. Simple vertical stack for now.
      const listEps = resEps.filter(
        (e) => !isDetailRoute(e.path) || e.method !== 'GET'
      )
      const detailEps = resEps.filter(
        (e) => isDetailRoute(e.path) && e.method === 'GET'
      )

      // Separate: list/collection ops on the left column, detail ops on the right
      const leftEps: EndpointItem[] = []
      const rightEps: EndpointItem[] = []

      for (const ep of resEps) {
        if (isDetailRoute(ep.path)) {
          rightEps.push(ep)
        } else {
          leftEps.push(ep)
        }
      }

      // If everything is on one side, just put them all in left column
      if (leftEps.length === 0 && rightEps.length > 0) {
        leftEps.push(...rightEps.splice(0))
      }

      const leftH = leftEps.length * (ENDPOINT_NODE_H + CLUSTER_GAP_Y)
      const rightH = rightEps.length * (ENDPOINT_NODE_H + CLUSTER_GAP_Y)
      const clusterH = Math.max(leftH, rightH, ENDPOINT_NODE_H)
      const clusterW =
        rightEps.length > 0
          ? ENDPOINT_NODE_W * 2 + CLUSTER_GAP_X
          : ENDPOINT_NODE_W

      const clusterX = col * (RESOURCE_CLUSTER_GAP_X + ENDPOINT_NODE_W)
      const clusterY = row * RESOURCE_CLUSTER_GAP_Y

      clusterLayouts.push({
        resource,
        endpoints: resEps,
        x: clusterX,
        y: clusterY,
        width: clusterW,
        height: clusterH,
      })

      const right = clusterX + clusterW
      const bottom = clusterY + clusterH
      if (right > maxGroupW) maxGroupW = right
      if (bottom > maxGroupH) maxGroupH = bottom
    }

    const groupW = maxGroupW + GROUP_PADDING_X * 2
    const groupH = maxGroupH + GROUP_PADDING_Y + GROUP_PADDING_BOTTOM

    // Create the group node
    nodes.push({
      id: groupNodeId,
      type: 'sourceGroup',
      position: { x: 0, y: globalSourceOffsetY },
      data: { label: sourceName, endpointCount: eps.length },
      style: {
        width: `${groupW}px`,
        height: `${groupH}px`,
        backgroundColor: 'rgba(99, 102, 241, 0.03)',
        borderRadius: '16px',
        border: '2px solid rgba(99, 102, 241, 0.1)',
        padding: '0',
      },
    })

    // --- Create endpoint nodes inside each cluster ---
    for (const cl of clusterLayouts) {
      const resEps = cl.endpoints

      // Split into left (collection) and right (detail) columns
      const leftEps: EndpointItem[] = []
      const rightEps: EndpointItem[] = []

      for (const ep of resEps) {
        if (isDetailRoute(ep.path)) {
          rightEps.push(ep)
        } else {
          leftEps.push(ep)
        }
      }

      if (leftEps.length === 0 && rightEps.length > 0) {
        leftEps.push(...rightEps.splice(0))
      }

      // Place left column endpoints
      for (let i = 0; i < leftEps.length; i++) {
        const ep = leftEps[i]
        const methodColor = METHOD_COLORS[ep.method] || '#9e9e9e'
        const epNodeId = `ep-${ep.id}`
        nodes.push({
          id: epNodeId,
          type: 'endpoint',
          parentNode: groupNodeId,
          extent: 'parent' as const,
          position: {
            x: GROUP_PADDING_X + cl.x,
            y: GROUP_PADDING_Y + cl.y + i * (ENDPOINT_NODE_H + CLUSTER_GAP_Y),
          },
          data: {
            ...ep,
            color: methodColor,
          },
          sourcePosition: Position.Right,
          targetPosition: Position.Left,
        })
      }

      // Place right column endpoints
      for (let i = 0; i < rightEps.length; i++) {
        const ep = rightEps[i]
        const methodColor = METHOD_COLORS[ep.method] || '#9e9e9e'
        const epNodeId = `ep-${ep.id}`
        nodes.push({
          id: epNodeId,
          type: 'endpoint',
          parentNode: groupNodeId,
          extent: 'parent' as const,
          position: {
            x: GROUP_PADDING_X + cl.x + ENDPOINT_NODE_W + CLUSTER_GAP_X,
            y: GROUP_PADDING_Y + cl.y + i * (ENDPOINT_NODE_H + CLUSTER_GAP_Y),
          },
          data: {
            ...ep,
            color: methodColor,
          },
          sourcePosition: Position.Right,
          targetPosition: Position.Left,
        })
      }

      // Same-resource edges: connect list GET to detail GET
      const listGet = leftEps.find((e) => e.method === 'GET')
      const detailGet = rightEps.find((e) => e.method === 'GET')
      if (listGet && detailGet) {
        edges.push({
          id: `same-${listGet.id}-${detailGet.id}`,
          source: `ep-${listGet.id}`,
          target: `ep-${detailGet.id}`,
          sourceHandle: 'right',
          targetHandle: 'left',
          type: 'smoothstep',
          animated: false,
          style: { stroke: '#a1a1aa', strokeWidth: 1.5 },
          label: '/{id}',
          labelStyle: { fontSize: '9px', fill: '#71717a', fontWeight: 500 },
          labelBgStyle: { fill: '#fff', fillOpacity: 0.9 },
          labelBgPadding: [3, 5] as [number, number],
        })
      }
    }

    // --- Relationship edges ---
    const epNodes = nodes.filter((n) => n.type === 'endpoint' && n.parentNode === groupNodeId)

    // FK edges from parameters
    for (const fromNode of epNodes) {
      const fromParams = fromNode.data.parameters || []
      for (const param of fromParams) {
        const pName: string = param.name || ''
        const fkTarget = detectFKFromParam(pName)
        if (!fkTarget) continue

        // Find a matching list endpoint for the target resource
        for (const toNode of epNodes) {
          if (toNode.id === fromNode.id) continue
          const toPath: string = toNode.data.path || ''
          const toResource = extractResource(toPath)
          // Only link to GET list endpoints for cleanliness
          if (
            toResource === fkTarget &&
            toNode.data.method === 'GET' &&
            !isDetailRoute(toPath)
          ) {
            const edgeId = `fk-${fromNode.id}-${toNode.id}-${pName}`
            if (!edges.find((e: any) => e.id === edgeId)) {
              edges.push({
                id: edgeId,
                source: fromNode.id,
                target: toNode.id,
                sourceHandle: 'top-out',
                targetHandle: 'top-in',
                type: 'smoothstep',
                animated: true,
                label: pName,
                labelStyle: { fontSize: '9px', fill: '#2563eb', fontWeight: 500 },
                labelBgStyle: { fill: '#fff', fillOpacity: 0.9 },
                labelBgPadding: [3, 5] as [number, number],
                style: {
                  stroke: '#2563eb',
                  strokeWidth: 1.5,
                  strokeDasharray: '6 3',
                },
                markerEnd: {
                  type: 'arrowclosed' as const,
                  color: '#2563eb',
                  width: 10,
                  height: 10,
                },
              })
            }
          }
        }
      }

      // Nested path edges: /posts/{id}/comments -> /posts
      const fromPath: string = fromNode.data.path || ''
      const parentPath = getParentResourcePath(fromPath)
      if (parentPath) {
        for (const toNode of epNodes) {
          if (toNode.id === fromNode.id) continue
          const toPath: string = toNode.data.path || ''
          if (toPath === parentPath && toNode.data.method === 'GET') {
            const edgeId = `parent-${fromNode.id}-${toNode.id}`
            if (!edges.find((e: any) => e.id === edgeId)) {
              edges.push({
                id: edgeId,
                source: toNode.id,
                target: fromNode.id,
                sourceHandle: 'bottom-out',
                targetHandle: 'bottom-in',
                type: 'smoothstep',
                animated: false,
                label: 'parent',
                labelStyle: { fontSize: '9px', fill: '#7c3aed', fontWeight: 500 },
                labelBgStyle: { fill: '#fff', fillOpacity: 0.9 },
                labelBgPadding: [3, 5] as [number, number],
                style: {
                  stroke: '#7c3aed',
                  strokeWidth: 1.5,
                  strokeDasharray: '4 4',
                },
                markerEnd: {
                  type: 'arrowclosed' as const,
                  color: '#7c3aed',
                  width: 10,
                  height: 10,
                },
              })
            }
          }
        }
      }
    }

    globalSourceOffsetY += groupH + 80
  }

  // --- Cross-source FK edges ---
  const allEpNodes = nodes.filter((n) => n.type === 'endpoint')
  for (const fromNode of allEpNodes) {
    const fromParams = fromNode.data.parameters || []
    for (const param of fromParams) {
      const pName: string = param.name || ''
      const fkTarget = detectFKFromParam(pName)
      if (!fkTarget) continue

      for (const toNode of allEpNodes) {
        if (toNode.id === fromNode.id) continue
        if (toNode.parentNode === fromNode.parentNode) continue // skip same-source (already handled)
        const toPath: string = toNode.data.path || ''
        const toResource = extractResource(toPath)
        if (
          toResource === fkTarget &&
          toNode.data.method === 'GET' &&
          !isDetailRoute(toPath)
        ) {
          const edgeId = `xfk-${fromNode.id}-${toNode.id}-${pName}`
          if (!edges.find((e: any) => e.id === edgeId)) {
            edges.push({
              id: edgeId,
              source: fromNode.id,
              target: toNode.id,
              sourceHandle: 'top-out',
              targetHandle: 'top-in',
              type: 'smoothstep',
              animated: true,
              label: pName,
              labelStyle: { fontSize: '9px', fill: '#2563eb', fontWeight: 500 },
              labelBgStyle: { fill: '#fff', fillOpacity: 0.9 },
              labelBgPadding: [3, 5] as [number, number],
              style: {
                stroke: '#2563eb',
                strokeWidth: 1.5,
                strokeDasharray: '6 3',
              },
              markerEnd: {
                type: 'arrowclosed' as const,
                color: '#2563eb',
                width: 10,
                height: 10,
              },
            })
          }
        }
      }
    }
  }

  return { nodes, edges }
})

const nodes = computed(() => graphElements.value.nodes)
const edges = computed(() => graphElements.value.edges)

function onNodeClick({ node }: { node: any }) {
  if (node.type === 'endpoint') {
    selectedEndpoint.value = node.data as SelectedEndpoint
  }
}

function closePanel() {
  selectedEndpoint.value = null
}

function formatJson(obj: any): string {
  if (!obj) return ''
  return JSON.stringify(obj, null, 2)
}

onMounted(async () => {
  await Promise.all([
    endpointsStore.fetchEndpoints(),
    swaggerStore.fetchSwaggers(),
  ])
  await nextTick()
  setTimeout(() => fitView({ padding: 0.15 }), 250)
})
</script>

<template>
  <div class="api-maps">
    <div class="maps-header">
      <div class="header-left">
        <h2 class="header-title">API Maps</h2>
        <span class="endpoint-count">{{ endpointsStore.endpoints.length }} endpoints</span>
      </div>
      <div class="header-actions">
        <button class="fit-btn" @click="fitView({ padding: 0.15 })" title="Fit to view">
          <i class="pi pi-expand"></i>
        </button>
      </div>
    </div>

    <div v-if="endpointsStore.isLoading" class="maps-loading">
      <i class="pi pi-spin pi-spinner"></i>
      <span>Loading API map...</span>
    </div>

    <div v-else-if="endpointsStore.endpoints.length === 0" class="maps-empty">
      <i class="pi pi-sitemap maps-empty-icon"></i>
      <p>No endpoints to visualize.</p>
      <p class="maps-empty-hint">Upload a Swagger spec to see your API map.</p>
    </div>

    <div v-else class="maps-container">
      <VueFlow
        :nodes="nodes"
        :edges="edges"
        :default-viewport="{ zoom: 0.7, x: 50, y: 50 }"
        :min-zoom="0.1"
        :max-zoom="2"
        @node-click="onNodeClick"
        fit-view-on-init
      >
        <template #node-sourceGroup="props">
          <SourceGroupNode :data="props.data" />
        </template>
        <template #node-endpoint="props">
          <EndpointNode :data="props.data" />
        </template>
        <Background :gap="20" :size="1" />
        <Controls :show-interactive="false" />
        <MiniMap
          :node-stroke-width="3"
          :pannable="true"
          :zoomable="true"
        />
      </VueFlow>

      <!-- Legend -->
      <div class="map-legend">
        <div class="legend-title">Legend</div>
        <div class="legend-section">
          <div class="legend-item">
            <span class="legend-swatch" style="background: #34a853"></span>
            <span>GET</span>
          </div>
          <div class="legend-item">
            <span class="legend-swatch" style="background: #1a73e8"></span>
            <span>POST</span>
          </div>
          <div class="legend-item">
            <span class="legend-swatch" style="background: #f59e0b"></span>
            <span>PUT</span>
          </div>
          <div class="legend-item">
            <span class="legend-swatch" style="background: #ea4335"></span>
            <span>DELETE</span>
          </div>
          <div class="legend-item">
            <span class="legend-swatch" style="background: #673ab7"></span>
            <span>PATCH</span>
          </div>
        </div>
        <div class="legend-section">
          <div class="legend-item">
            <span class="legend-line legend-solid"></span>
            <span>Hierarchy</span>
          </div>
          <div class="legend-item">
            <span class="legend-line legend-dashed-blue"></span>
            <span>FK reference</span>
          </div>
          <div class="legend-item">
            <span class="legend-line legend-dashed-purple"></span>
            <span>Parent resource</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Detail panel -->
    <transition name="panel-slide">
      <div v-if="selectedEndpoint" class="detail-panel">
        <div class="detail-header">
          <div class="detail-title-row">
            <span
              class="method-badge"
              :style="{
                background: selectedEndpoint.color,
                color: selectedEndpoint.method === 'PUT' ? '#333' : '#fff',
              }"
            >
              {{ selectedEndpoint.method }}
            </span>
            <span class="detail-path">{{ selectedEndpoint.path }}</span>
          </div>
          <button class="close-btn" @click="closePanel" title="Close">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <div class="detail-body">
          <p v-if="selectedEndpoint.summary" class="detail-summary">
            {{ selectedEndpoint.summary }}
          </p>
          <p v-if="selectedEndpoint.description" class="detail-description">
            {{ selectedEndpoint.description }}
          </p>

          <div
            v-if="selectedEndpoint.parameters && selectedEndpoint.parameters.length"
            class="detail-section"
          >
            <h4 class="section-title">Parameters</h4>
            <div class="params-list">
              <div
                v-for="p in selectedEndpoint.parameters"
                :key="p.name"
                class="param-row"
              >
                <code class="param-name">{{ p.name }}</code>
                <span class="param-in">{{ p.in }}</span>
                <span v-if="p.schema?.type || p.type" class="param-type">{{
                  p.schema?.type || p.type
                }}</span>
                <span v-if="p.required" class="param-required">required</span>
              </div>
            </div>
          </div>

          <div v-if="selectedEndpoint.request_body" class="detail-section">
            <h4 class="section-title">Request Body</h4>
            <pre class="detail-code">{{ formatJson(selectedEndpoint.request_body) }}</pre>
          </div>

          <div v-if="selectedEndpoint.response_schema" class="detail-section">
            <h4 class="section-title">Response Schema</h4>
            <pre class="detail-code">{{ formatJson(selectedEndpoint.response_schema) }}</pre>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.api-maps {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  position: relative;
}

.maps-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--color-border-light, #eee);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary, #1a1a1a);
  margin: 0;
}

.endpoint-count {
  font-size: 13px;
  color: var(--color-text-tertiary, #999);
  background: var(--color-bg-tertiary, #f5f5f5);
  padding: 3px 10px;
  border-radius: 12px;
  font-weight: 500;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.fit-btn {
  width: 34px;
  height: 34px;
  border: 1px solid var(--color-border-light, #e0e0e0);
  background: var(--color-bg, #fff);
  border-radius: 8px;
  color: var(--color-text-secondary, #666);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.fit-btn:hover {
  background: var(--color-bg-tertiary, #f5f5f5);
  color: var(--color-text-primary, #1a1a1a);
}

/* Loading / Empty states */
.maps-loading,
.maps-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--color-text-tertiary, #999);
  font-size: 14px;
}

.maps-empty-icon {
  font-size: 40px;
  color: var(--color-border, #ddd);
  margin-bottom: 8px;
}

.maps-empty-hint {
  font-size: 13px;
  color: var(--color-text-tertiary, #aaa);
}

/* Flow container */
.maps-container {
  flex: 1;
  width: 100%;
  position: relative;
}

/* Vue Flow overrides */
.maps-container :deep(.vue-flow__minimap) {
  background: rgba(30, 30, 30, 0.85);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.maps-container :deep(.vue-flow__controls) {
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* Source group node styling */
.maps-container :deep(.vue-flow__node-sourceGroup) {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-secondary, #666);
  pointer-events: none;
}

.maps-container :deep(.vue-flow__node-sourceGroup > div) {
  pointer-events: none;
}

/* Legend */
.map-legend {
  position: absolute;
  bottom: 16px;
  left: 16px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(8px);
  border: 1px solid #e4e4e7;
  border-radius: 10px;
  padding: 10px 14px;
  z-index: 10;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  font-size: 11px;
  min-width: 140px;
}

.legend-title {
  font-weight: 600;
  color: #3f3f46;
  margin-bottom: 6px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.legend-section {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-bottom: 6px;
}

.legend-section:last-child {
  margin-bottom: 0;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #52525b;
}

.legend-swatch {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  flex-shrink: 0;
}

.legend-line {
  width: 20px;
  height: 0;
  border-top: 2px solid;
  flex-shrink: 0;
}

.legend-solid {
  border-color: #a1a1aa;
}

.legend-dashed-blue {
  border-color: #2563eb;
  border-top-style: dashed;
}

.legend-dashed-purple {
  border-color: #7c3aed;
  border-top-style: dashed;
}

/* Detail panel */
.detail-panel {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 380px;
  background: var(--color-bg, #fff);
  border-left: 1px solid var(--color-border-light, #eee);
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  z-index: 20;
  overflow: hidden;
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border-light, #eee);
  flex-shrink: 0;
}

.detail-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.method-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.detail-path {
  font-size: 14px;
  font-weight: 500;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  color: var(--color-text-primary, #1a1a1a);
  word-break: break-all;
}

.close-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: none;
  border-radius: 6px;
  color: var(--color-text-tertiary, #999);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  margin-left: 8px;
  transition: background 0.15s, color 0.15s;
}

.close-btn:hover {
  background: var(--color-bg-tertiary, #f5f5f5);
  color: var(--color-text-primary, #1a1a1a);
}

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-summary {
  font-size: 14px;
  color: var(--color-text-primary, #1a1a1a);
  line-height: 1.5;
  margin: 0;
}

.detail-description {
  font-size: 13px;
  color: var(--color-text-secondary, #666);
  line-height: 1.5;
  margin: 0;
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary, #666);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0;
}

.params-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.param-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--color-bg-secondary, #fafafa);
  border: 1px solid var(--color-border-light, #eee);
  border-radius: 6px;
  font-size: 13px;
}

.param-name {
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-weight: 500;
  color: var(--color-text-primary, #1a1a1a);
  font-size: 12px;
}

.param-in {
  font-size: 11px;
  color: var(--color-text-tertiary, #999);
  background: var(--color-bg-tertiary, #f0f0f0);
  padding: 1px 6px;
  border-radius: 4px;
}

.param-type {
  font-size: 11px;
  color: #2563eb;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
}

.param-required {
  font-size: 10px;
  color: #ea4335;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.detail-code {
  background: var(--color-bg-tertiary, #f5f5f5);
  border: 1px solid var(--color-border-light, #eee);
  border-radius: 8px;
  padding: 12px;
  font-size: 12px;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  overflow-x: auto;
  color: var(--color-text-primary, #1a1a1a);
  line-height: 1.5;
  max-height: 240px;
  overflow-y: auto;
  margin: 0;
}

/* Panel slide transition */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: transform 0.25s ease, opacity 0.25s ease;
}

.panel-slide-enter-from,
.panel-slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

@media (max-width: 768px) {
  .detail-panel {
    width: 100%;
  }
}
</style>
