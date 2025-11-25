/**
 * Run Detail Page
 *
 * Detailed view of a simulation run with charts, predictions,
 * live network visualization, and ML control status.
 */

import { useState, useEffect, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeftIcon, CpuChipIcon, SignalIcon } from '@heroicons/react/24/outline';
import { useRun, useRunTimeseries, useEdgeHistory } from '../hooks/useFirestore';
import { SpeedChart, HeatmapChart, TopCongestedChart } from '../components/Charts';
import { LiveNetworkMap } from '../components/LiveNetworkMap';
import { getEdges, predictTraffic, getLiveState, type LiveState } from '../utils/api';
import type { EdgeInfo, Prediction } from '../types';

export default function RunDetail() {
  const { runId } = useParams<{ runId: string }>();
  const { run, loading: runLoading } = useRun(runId || null);
  const { timeseries, loading: timeseriesLoading } = useRunTimeseries(runId || null);

  const [edges, setEdges] = useState<EdgeInfo[]>([]);
  const [selectedEdge, setSelectedEdge] = useState<string>('');
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [predicting, setPredicting] = useState(false);
  const [liveState, setLiveState] = useState<LiveState | null>(null);

  // Load edges
  useEffect(() => {
    getEdges()
      .then((data) => {
        setEdges(data.edges);
        if (data.edges.length > 0) {
          setSelectedEdge(data.edges[0].edgeId);
        }
      })
      .catch(console.error);
  }, []);

  // Poll for live state when run is active
  useEffect(() => {
    if (!runId || run?.status === 'completed' || run?.status === 'failed') return;

    const fetchLiveState = () => {
      getLiveState(runId)
        .then(setLiveState)
        .catch(() => {});
    };

    fetchLiveState();
    const interval = setInterval(fetchLiveState, 2000);
    return () => clearInterval(interval);
  }, [runId, run?.status]);

  // Get edge history for selected edge
  const { edgeHistory } = useEdgeHistory(runId || null, selectedEdge);

  // Get predictions when edge history changes
  useEffect(() => {
    if (edgeHistory.length < 6 || !selectedEdge) {
      setPredictions([]);
      return;
    }

    setPredicting(true);
    predictTraffic(
      [
        {
          edgeId: selectedEdge,
          speeds: edgeHistory.map((h) => h.speed),
          queueLens: edgeHistory.map((h) => h.queueLen),
          eventFlags: edgeHistory.map((h) => h.hasEvent),
        },
      ],
      300, // 5 minutes horizon
      60   // 1 minute steps
    )
      .then((data) => {
        setPredictions(data.predictions || []);
      })
      .catch(console.error)
      .finally(() => setPredicting(false));
  }, [selectedEdge, edgeHistory]);

  // Calculate heatmap data
  const heatmapData = useMemo(() => {
    if (timeseries.length === 0) return { times: [], edges: [], data: [] };

    // Get key edges for heatmap
    const keyEdges = edges.slice(0, 8).map((e) => e.edgeId);
    const times = timeseries.slice(0, 20).map((t) => t.t);

    const data: number[][] = times.map((_, timeIdx) => {
      return keyEdges.map((edgeId) => {
        const point = timeseries[timeIdx];
        const edgeData = point?.metricsByEdge?.find((e) => e.edgeId === edgeId);
        // Congestion index: higher queue + lower speed = more congested
        return edgeData ? edgeData.queueLen + (20 - edgeData.avgSpeed) / 2 : 0;
      });
    });

    return {
      times,
      edges: keyEdges.map((id) => edges.find((e) => e.edgeId === id)?.label || id),
      data,
    };
  }, [timeseries, edges]);

  // Calculate top congested edges
  const topCongested = useMemo(() => {
    if (timeseries.length === 0) return [];

    // Aggregate queue lengths by edge
    const edgeQueues: Record<string, number[]> = {};

    timeseries.forEach((point) => {
      point.metricsByEdge.forEach((edge) => {
        if (!edgeQueues[edge.edgeId]) {
          edgeQueues[edge.edgeId] = [];
        }
        edgeQueues[edge.edgeId].push(edge.queueLen);
      });
    });

    return Object.entries(edgeQueues)
      .map(([edgeId, queues]) => ({
        edgeId,
        label: edges.find((e) => e.edgeId === edgeId)?.label || edgeId,
        value: queues.reduce((a, b) => a + b, 0) / queues.length,
      }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 10);
  }, [timeseries, edges]);

  const loading = runLoading || timeseriesLoading;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  if (!run) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
          Run Not Found
        </h2>
        <Link to="/runs" className="text-primary-600 hover:underline">
          Back to Runs
        </Link>
      </div>
    );
  }

  // Prepare data for actual vs predicted chart
  const actualTimes = edgeHistory.map((h) => h.t);
  const actualSpeeds = edgeHistory.map((h) => h.speed);

  // Extend with predictions
  const lastTime = actualTimes[actualTimes.length - 1] || 0;
  const predictedTimes = predictions.map((p) => lastTime + p.t);
  const predictedSpeeds = predictions.map((p) => p.speed);

  const combinedTimes = [...actualTimes, ...predictedTimes];
  const combinedActual = [...actualSpeeds, ...Array(predictedSpeeds.length).fill(null)];
  const combinedPredicted = [...Array(actualSpeeds.length).fill(null), ...predictedSpeeds];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-4">
        <Link
          to="/runs"
          className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
        >
          <ArrowLeftIcon className="w-5 h-5 text-gray-500" />
        </Link>
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Run: {runId}
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Status:{' '}
            <span
              className={`font-medium ${
                run.status === 'completed'
                  ? 'text-green-600'
                  : run.status === 'running'
                  ? 'text-yellow-600'
                  : run.status === 'failed'
                  ? 'text-red-600'
                  : 'text-gray-600'
              }`}
            >
              {run.status}
            </span>
          </p>
        </div>
      </div>

      {/* Live Network Map with Traffic Lights */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <SignalIcon className="w-5 h-5" />
            Live Traffic Network
          </h3>
          {(liveState?.adaptiveControl || run.summary?.adaptiveControl) && (
            <div className="flex items-center gap-2 px-3 py-1 bg-green-100 dark:bg-green-900/30 rounded-full">
              <CpuChipIcon className="w-4 h-4 text-green-600 dark:text-green-400" />
              <span className="text-sm font-medium text-green-700 dark:text-green-300">
                ML Adaptive Control {run.summary?.mlModel ? `(${run.summary.mlModel})` : ''}
              </span>
            </div>
          )}
        </div>
        <LiveNetworkMap
          runId={runId}
          selectedEdge={selectedEdge}
          onEdgeSelect={setSelectedEdge}
          height={400}
          refreshInterval={2000}
        />
      </div>

      {/* Summary Card */}
      {run.summary && (
        <div className="card p-6">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-4">
            Run Summary
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Avg Speed</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white">
                {run.summary.avgSpeed.toFixed(2)} m/s
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Max Delay</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white">
                {run.summary.maxDelay.toFixed(0)} s
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Avg Delay</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white">
                {run.summary.avgDelay.toFixed(1)} s
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Max Queue</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white">
                {run.summary.maxQueueLength}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Timesteps</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white">
                {run.summary.totalTimesteps}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Control Mode</p>
              <p className={`text-lg font-semibold ${run.summary.adaptiveControl ? 'text-green-600' : 'text-gray-900 dark:text-white'}`}>
                {run.summary.adaptiveControl ? 'ML Adaptive' : 'Fixed Timing'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Edge Selector and Actual vs Predicted Chart */}
      <div className="card p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
          <h3 className="font-semibold text-gray-900 dark:text-white">
            Actual vs Predicted Speed
          </h3>
          <select
            value={selectedEdge}
            onChange={(e) => setSelectedEdge(e.target.value)}
            className="input w-full sm:w-64"
          >
            {edges.map((edge) => (
              <option key={edge.edgeId} value={edge.edgeId}>
                {edge.label}
              </option>
            ))}
          </select>
        </div>

        {predicting && (
          <div className="text-sm text-gray-500 mb-2">Generating predictions...</div>
        )}

        {edgeHistory.length > 0 ? (
          <SpeedChart
            times={combinedTimes}
            speeds={combinedActual as number[]}
            predictedSpeeds={combinedPredicted as number[]}
            title=""
            height={350}
          />
        ) : (
          <div className="h-64 flex items-center justify-center text-gray-500">
            No data available for selected edge
          </div>
        )}
      </div>

      {/* Heatmap and Top Congested */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Heatmap */}
        <div className="card p-4">
          {heatmapData.times.length > 0 ? (
            <HeatmapChart
              times={heatmapData.times}
              edges={heatmapData.edges}
              data={heatmapData.data}
              title="Congestion Heatmap (Time vs Roads)"
              height={400}
            />
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500">
              Not enough data for heatmap
            </div>
          )}
        </div>

        {/* Top Congested */}
        <div className="card p-4">
          {topCongested.length > 0 ? (
            <TopCongestedChart
              edges={topCongested}
              title="Top 10 Most Congested Roads"
              height={400}
            />
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500">
              Not enough data for ranking
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
