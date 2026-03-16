<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart, ScatterChart, RadarChart, GaugeChart, FunnelChart, TreemapChart, HeatmapChart, SankeyChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent, DatasetComponent, ToolboxComponent, VisualMapComponent, DataZoomComponent } from 'echarts/components'

use([
  CanvasRenderer,
  BarChart, LineChart, PieChart, ScatterChart, RadarChart, GaugeChart, FunnelChart, TreemapChart, HeatmapChart, SankeyChart,
  TitleComponent, TooltipComponent, LegendComponent, GridComponent, DatasetComponent, ToolboxComponent, VisualMapComponent, DataZoomComponent,
])

const COLORS = ['#1a73e8', '#34a853', '#fbbc04', '#ea4335', '#673ab7', '#00bcd4', '#ff5722', '#795548']

const props = defineProps<{
  data: Record<string, any>
  metadata?: Record<string, any>
}>()

// Responsive detection
const isMobile = ref(false)
const isTablet = ref(false)

function updateBreakpoints() {
  const width = window.innerWidth
  isMobile.value = width <= 640
  isTablet.value = width > 640 && width <= 768
}

onMounted(() => {
  updateBreakpoints()
  window.addEventListener('resize', updateBreakpoints)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateBreakpoints)
})

const chartHeight = computed(() => {
  if (isMobile.value) return '280px'
  if (isTablet.value) return '320px'
  return '400px'
})

const chartOption = computed(() => {
  // If native ECharts option provided, use it directly
  if (props.data.option) {
    const option = { ...props.data.option, color: props.data.option.color || COLORS }
    return applyResponsiveOptions(option)
  }

  // Legacy format conversion (labels + datasets)
  const chartType = props.data.chart_type || props.data.chartType || props.data.type || 'bar'
  const labels = props.data.labels || []
  const datasets = props.data.datasets || []

  const baseOption = buildChartOption(chartType, labels, datasets)
  return applyResponsiveOptions(baseOption)
})

function buildChartOption(chartType: string, labels: string[], datasets: any[]) {
  if (chartType === 'pie') {
    const pieData = labels.map((name: string, i: number) => ({
      value: datasets[0]?.data?.[i] || 0,
      name,
    }))
    return {
      color: COLORS,
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: { orient: 'vertical', left: 'left' },
      series: [{ type: 'pie', radius: ['40%', '70%'], data: pieData, emphasis: { itemStyle: { shadowBlur: 10 } } }],
    }
  }

  if (chartType === 'scatter') {
    return {
      color: COLORS,
      tooltip: { trigger: 'item' },
      xAxis: { type: 'value' },
      yAxis: { type: 'value' },
      series: datasets.map((ds: any) => ({
        type: 'scatter',
        name: ds.label || '',
        data: ds.data,
      })),
    }
  }

  // Default: bar, line, area
  return {
    color: COLORS,
    tooltip: { trigger: 'axis' },
    legend: {},
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value' },
    series: datasets.map((ds: any) => ({
      name: ds.label || '',
      type: chartType === 'area' ? 'line' : chartType,
      data: ds.data,
      ...(chartType === 'area' ? { areaStyle: {} } : {}),
      smooth: chartType === 'line' || chartType === 'area',
    })),
  }
}

function applyResponsiveOptions(option: any) {
  const responsiveOption = { ...option }

  if (isMobile.value) {
    // Mobile: larger fonts for readability
    responsiveOption.textStyle = { fontSize: 12 }
    
    if (responsiveOption.xAxis) {
      if (Array.isArray(responsiveOption.xAxis)) {
        responsiveOption.xAxis = responsiveOption.xAxis.map((axis: any) => ({
          ...axis,
          axisLabel: { ...axis.axisLabel, fontSize: 11 },
        }))
      } else {
        responsiveOption.xAxis = {
          ...responsiveOption.xAxis,
          axisLabel: { ...responsiveOption.xAxis.axisLabel, fontSize: 11 },
        }
      }
    }

    if (responsiveOption.yAxis) {
      if (Array.isArray(responsiveOption.yAxis)) {
        responsiveOption.yAxis = responsiveOption.yAxis.map((axis: any) => ({
          ...axis,
          axisLabel: { ...axis.axisLabel, fontSize: 11 },
        }))
      } else {
        responsiveOption.yAxis = {
          ...responsiveOption.yAxis,
          axisLabel: { ...responsiveOption.yAxis.axisLabel, fontSize: 11 },
        }
      }
    }

    // Mobile: move legend to bottom if many items
    if (responsiveOption.legend) {
      const seriesCount = responsiveOption.series?.length || 0
      if (seriesCount > 3) {
        responsiveOption.legend = {
          ...responsiveOption.legend,
          orient: 'horizontal',
          bottom: 0,
          left: 'center',
          itemWidth: 15,
          itemHeight: 10,
          textStyle: { fontSize: 10 },
        }
      }
    }

    // Mobile: smaller toolbox or remove it
    if (responsiveOption.toolbox) {
      responsiveOption.toolbox = {
        ...responsiveOption.toolbox,
        itemSize: 12,
        right: 5,
        top: 5,
      }
      // Reduce features on mobile
      if (responsiveOption.toolbox.feature) {
        const { saveAsImage, dataView, restore } = responsiveOption.toolbox.feature
        responsiveOption.toolbox.feature = { saveAsImage, dataView, restore }
      }
    }

    // Mobile: add pinch-to-zoom and touch-drag support
    if (!responsiveOption.dataZoom) {
      responsiveOption.dataZoom = []
    }
    
    // Add inside dataZoom for pinch-to-zoom on touch devices
    const hasDataZoom = responsiveOption.dataZoom && responsiveOption.dataZoom.length > 0
    if (!hasDataZoom) {
      // For charts with axes, add dataZoom
      if (responsiveOption.xAxis || responsiveOption.yAxis) {
        responsiveOption.dataZoom = [
          {
            type: 'inside',
            xAxisIndex: 0,
            start: 0,
            end: 100,
            zoomOnMouseWheel: true,
            moveOnMouseMove: true,
            moveOnMouseWheel: true,
            preventDefaultMouseMove: false,
          },
          {
            type: 'inside',
            yAxisIndex: 0,
            start: 0,
            end: 100,
            zoomOnMouseWheel: true,
            moveOnMouseMove: true,
            moveOnMouseWheel: true,
            preventDefaultMouseMove: false,
          }
        ]
      }
    }

    // Adjust grid for mobile
    if (responsiveOption.grid) {
      responsiveOption.grid = {
        ...responsiveOption.grid,
        top: responsiveOption.title ? 40 : 30,
        bottom: responsiveOption.legend?.orient === 'horizontal' ? 50 : 20,
        left: 50,
        right: 10,
      }
    }
  }

  return responsiveOption
}

const title = computed(() => props.data.title || props.metadata?.title || '')
</script>

<template>
  <div class="chart-result">
    <div v-if="title" class="chart-title">{{ title }}</div>
    <VChart 
      class="chart" 
      :option="chartOption" 
      autoresize 
      :style="{ height: chartHeight }"
      :class="{ 'chart-mobile': isMobile }"
    />
  </div>
</template>

<style scoped>
.chart-result {
  padding: 16px;
  min-height: 0;
  overflow: hidden;
}

.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 12px;
}

.chart {
  width: 100%;
  height: 400px;
  min-width: 0;
}

/* Tablet styles (641-768px) */
@media (max-width: 768px) {
  .chart-result {
    padding: 14px;
  }

  .chart-title {
    font-size: 13px;
    margin-bottom: 10px;
  }

  .chart {
    height: 320px;
    min-height: 320px;
  }
}

/* Mobile styles (< 640px) */
@media (max-width: 640px) {
  .chart-result {
    padding: 12px;
    min-height: 0;
  }

  .chart-title {
    font-size: 13px;
    margin-bottom: 8px;
  }

  .chart {
    height: 280px !important;
    min-height: 280px;
  }

  /* Ensure chart doesn't overflow */
  :deep(.echarts) {
    width: 100% !important;
    max-width: 100%;
  }
}
</style>
