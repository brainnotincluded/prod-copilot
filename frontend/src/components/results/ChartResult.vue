<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart, ScatterChart, RadarChart, GaugeChart, FunnelChart, TreemapChart, HeatmapChart, SankeyChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent, DatasetComponent, ToolboxComponent, VisualMapComponent } from 'echarts/components'

use([
  CanvasRenderer,
  BarChart, LineChart, PieChart, ScatterChart, RadarChart, GaugeChart, FunnelChart, TreemapChart, HeatmapChart, SankeyChart,
  TitleComponent, TooltipComponent, LegendComponent, GridComponent, DatasetComponent, ToolboxComponent, VisualMapComponent,
])

const COLORS = ['#1a73e8', '#34a853', '#fbbc04', '#ea4335', '#673ab7', '#00bcd4', '#ff5722', '#795548']

const props = defineProps<{
  data: Record<string, any>
  metadata?: Record<string, any>
}>()

const chartOption = computed(() => {
  // If native ECharts option provided, use it directly
  if (props.data.option) {
    return { ...props.data.option, color: props.data.option.color || COLORS }
  }

  // Legacy format conversion (labels + datasets)
  const chartType = props.data.chart_type || props.data.chartType || props.data.type || 'bar'
  const labels = props.data.labels || []
  const datasets = props.data.datasets || []

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
})

const title = computed(() => props.data.title || props.metadata?.title || '')
</script>

<template>
  <div class="chart-result">
    <div v-if="title" class="chart-title">{{ title }}</div>
    <VChart class="chart" :option="chartOption" autoresize />
  </div>
</template>

<style scoped>
.chart-result {
  padding: 16px;
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
}
</style>
