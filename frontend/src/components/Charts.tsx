/**
 * ECharts Components for Traffic Visualization
 */

import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';

// ============================================================================
// Speed vs Time Line Chart
// ============================================================================

interface SpeedChartProps {
  times: number[];
  speeds: number[];
  predictedSpeeds?: number[];
  title?: string;
  height?: number;
}

export function SpeedChart({
  times,
  speeds,
  predictedSpeeds,
  title = 'Average Speed vs Time',
  height = 300,
}: SpeedChartProps) {
  const series: EChartsOption['series'] = [
    {
      name: 'Actual Speed',
      type: 'line',
      data: speeds,
      smooth: true,
      lineStyle: { width: 2 },
      itemStyle: { color: '#0ea5e9' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(14, 165, 233, 0.3)' },
            { offset: 1, color: 'rgba(14, 165, 233, 0.05)' },
          ],
        },
      },
    },
  ];

  if (predictedSpeeds) {
    series.push({
      name: 'Predicted Speed',
      type: 'line',
      data: predictedSpeeds,
      smooth: true,
      lineStyle: { width: 2, type: 'dashed' },
      itemStyle: { color: '#8b5cf6' },
    });
  }

  const option: EChartsOption = {
    title: {
      text: title,
      left: 'center',
      textStyle: { fontSize: 14, fontWeight: 500 },
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const p = params as Array<{ seriesName: string; value: number; axisValue: number }>;
        let html = `<strong>Time: ${formatTime(p[0].axisValue)}</strong><br/>`;
        p.forEach((item) => {
          html += `${item.seriesName}: ${item.value?.toFixed(1)} m/s<br/>`;
        });
        return html;
      },
    },
    legend: {
      bottom: 0,
      data: predictedSpeeds ? ['Actual Speed', 'Predicted Speed'] : ['Actual Speed'],
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: times.map(formatTime),
      axisLabel: { rotate: 45 },
    },
    yAxis: {
      type: 'value',
      name: 'Speed (m/s)',
      min: 0,
    },
    series,
  };

  return <ReactECharts option={option} style={{ height }} />;
}

// ============================================================================
// Queue Length Chart
// ============================================================================

interface QueueChartProps {
  times: number[];
  queues: number[];
  title?: string;
  height?: number;
}

export function QueueChart({
  times,
  queues,
  title = 'Total Queue Length vs Time',
  height = 300,
}: QueueChartProps) {
  const option: EChartsOption = {
    title: {
      text: title,
      left: 'center',
      textStyle: { fontSize: 14, fontWeight: 500 },
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const p = params as Array<{ value: number; axisValue: number }>;
        return `<strong>Time: ${formatTime(p[0].axisValue)}</strong><br/>Queue: ${p[0].value} vehicles`;
      },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '10%',
      top: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: times.map(formatTime),
      axisLabel: { rotate: 45 },
    },
    yAxis: {
      type: 'value',
      name: 'Vehicles',
      min: 0,
    },
    series: [
      {
        name: 'Queue Length',
        type: 'bar',
        data: queues,
        itemStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: '#f97316' },
              { offset: 1, color: '#fb923c' },
            ],
          },
        },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height }} />;
}

// ============================================================================
// Heatmap Chart (Time vs Edges)
// ============================================================================

interface HeatmapChartProps {
  times: number[];
  edges: string[];
  data: number[][]; // data[timeIdx][edgeIdx] = value
  title?: string;
  height?: number;
}

export function HeatmapChart({
  times,
  edges,
  data,
  title = 'Congestion Heatmap',
  height = 400,
}: HeatmapChartProps) {
  // Transform data for ECharts: [x, y, value]
  const heatmapData: [number, number, number][] = [];

  for (let i = 0; i < times.length; i++) {
    for (let j = 0; j < edges.length; j++) {
      heatmapData.push([i, j, data[i]?.[j] || 0]);
    }
  }

  const maxValue = Math.max(...heatmapData.map((d) => d[2]));

  const option: EChartsOption = {
    title: {
      text: title,
      left: 'center',
      textStyle: { fontSize: 14, fontWeight: 500 },
    },
    tooltip: {
      position: 'top',
      formatter: (params: unknown) => {
        const p = params as { data: [number, number, number] };
        return `${edges[p.data[1]]}<br/>Time: ${formatTime(times[p.data[0]])}<br/>Congestion: ${p.data[2].toFixed(1)}`;
      },
    },
    grid: {
      left: '15%',
      right: '10%',
      bottom: '15%',
      top: '10%',
    },
    xAxis: {
      type: 'category',
      data: times.map(formatTime),
      splitArea: { show: true },
      axisLabel: { rotate: 45 },
    },
    yAxis: {
      type: 'category',
      data: edges,
      splitArea: { show: true },
    },
    visualMap: {
      min: 0,
      max: maxValue || 10,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: '0%',
      inRange: {
        color: ['#d1fae5', '#fef3c7', '#fecaca', '#ef4444'],
      },
    },
    series: [
      {
        name: 'Congestion',
        type: 'heatmap',
        data: heatmapData,
        label: { show: false },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
          },
        },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height }} />;
}

// ============================================================================
// Bar Chart for Top Congested Edges
// ============================================================================

interface TopCongestedChartProps {
  edges: Array<{ edgeId: string; label: string; value: number }>;
  title?: string;
  height?: number;
}

export function TopCongestedChart({
  edges,
  title = 'Top Congested Roads',
  height = 300,
}: TopCongestedChartProps) {
  const sortedEdges = [...edges].sort((a, b) => b.value - a.value).slice(0, 10);

  const option: EChartsOption = {
    title: {
      text: title,
      left: 'center',
      textStyle: { fontSize: 14, fontWeight: 500 },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'value',
      name: 'Avg Queue',
    },
    yAxis: {
      type: 'category',
      data: sortedEdges.map((e) => e.label || e.edgeId),
      inverse: true,
    },
    series: [
      {
        name: 'Queue Length',
        type: 'bar',
        data: sortedEdges.map((e) => e.value),
        itemStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 1,
            y2: 0,
            colorStops: [
              { offset: 0, color: '#ef4444' },
              { offset: 1, color: '#f97316' },
            ],
          },
        },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height }} />;
}

// ============================================================================
// Comparison Line Chart (Multiple Series)
// ============================================================================

interface ComparisonChartProps {
  series: Array<{
    name: string;
    data: Array<{ t: number; value: number }>;
  }>;
  title?: string;
  yAxisName?: string;
  height?: number;
}

export function ComparisonChart({
  series,
  title = 'Run Comparison',
  yAxisName = 'Value',
  height = 350,
}: ComparisonChartProps) {
  // Get all unique time points
  const allTimes = new Set<number>();
  series.forEach((s) => s.data.forEach((d) => allTimes.add(d.t)));
  const times = Array.from(allTimes).sort((a, b) => a - b);

  const colors = ['#0ea5e9', '#8b5cf6', '#f97316', '#10b981', '#ef4444'];

  const echartsSeries = series.map((s, idx) => ({
    name: s.name,
    type: 'line' as const,
    data: times.map((t) => {
      const point = s.data.find((d) => d.t === t);
      return point ? point.value : null;
    }),
    smooth: true,
    lineStyle: { width: 2 },
    itemStyle: { color: colors[idx % colors.length] },
  }));

  const option: EChartsOption = {
    title: {
      text: title,
      left: 'center',
      textStyle: { fontSize: 14, fontWeight: 500 },
    },
    tooltip: {
      trigger: 'axis',
    },
    legend: {
      bottom: 0,
      data: series.map((s) => s.name),
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: times.map(formatTime),
      axisLabel: { rotate: 45 },
    },
    yAxis: {
      type: 'value',
      name: yAxisName,
    },
    series: echartsSeries,
  };

  return <ReactECharts option={option} style={{ height }} />;
}

// ============================================================================
// Radar Chart for KPI Comparison
// ============================================================================

interface RadarChartProps {
  runs: Array<{
    name: string;
    avgSpeed: number;
    avgDelay: number;
    maxQueueLength: number;
  }>;
  title?: string;
  height?: number;
}

export function RadarChart({
  runs,
  title = 'KPI Comparison',
  height = 350,
}: RadarChartProps) {
  // Normalize values to 0-100 scale
  const maxSpeed = Math.max(...runs.map((r) => r.avgSpeed));
  const maxDelay = Math.max(...runs.map((r) => r.avgDelay));
  const maxQueue = Math.max(...runs.map((r) => r.maxQueueLength));

  const colors = ['#0ea5e9', '#8b5cf6', '#f97316', '#10b981', '#ef4444'];

  const option: EChartsOption = {
    title: {
      text: title,
      left: 'center',
      textStyle: { fontSize: 14, fontWeight: 500 },
    },
    legend: {
      bottom: 0,
      data: runs.map((r) => r.name),
    },
    radar: {
      indicator: [
        { name: 'Avg Speed', max: maxSpeed * 1.2 },
        { name: 'Low Delay', max: maxDelay * 1.2 },
        { name: 'Low Queue', max: maxQueue * 1.2 },
      ],
      center: ['50%', '50%'],
      radius: '60%',
    },
    series: [
      {
        type: 'radar',
        data: runs.map((run, idx) => ({
          name: run.name,
          value: [
            run.avgSpeed,
            maxDelay - run.avgDelay, // Invert so higher is better
            maxQueue - run.maxQueueLength, // Invert so higher is better
          ],
          lineStyle: { color: colors[idx % colors.length] },
          itemStyle: { color: colors[idx % colors.length] },
          areaStyle: { color: colors[idx % colors.length], opacity: 0.2 },
        })),
      },
    ],
  };

  return <ReactECharts option={option} style={{ height }} />;
}

// ============================================================================
// Utility Functions
// ============================================================================

function formatTime(seconds: number): string {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`;
}
