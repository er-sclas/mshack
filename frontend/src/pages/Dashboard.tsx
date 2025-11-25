/**
 * Dashboard Page
 *
 * Main dashboard with KPIs and charts for traffic monitoring.
 */

import { useState, useMemo } from 'react';
import {
  BoltIcon,
  ClockIcon,
  QueueListIcon,
  TruckIcon,
} from '@heroicons/react/24/outline';
import KPICard from '../components/KPICard';
import { SpeedChart, QueueChart } from '../components/Charts';
import RegionFilter from '../components/RegionFilter';
import { useRuns, useRunTimeseries, useRegionMetrics } from '../hooks/useFirestore';
import type { Region } from '../types';

export default function Dashboard() {
  const [selectedRegion, setSelectedRegion] = useState<Region>('all');
  const { runs, loading: runsLoading } = useRuns({ status: 'completed', maxResults: 10 });

  // Get the most recent completed run
  const latestRun = runs[0];
  const { timeseries, loading: timeseriesLoading } = useRunTimeseries(
    latestRun?.id || null
  );

  // Get region-filtered metrics
  const regionMetrics = useRegionMetrics(timeseries, selectedRegion);

  // Calculate KPIs from latest data point
  const kpis = useMemo(() => {
    if (timeseries.length === 0) {
      return { avgSpeed: 0, totalDelay: 0, maxQueue: 0, numVehicles: 0 };
    }

    const latest = timeseries[timeseries.length - 1];
    const avgSpeeds = regionMetrics.avgSpeeds;
    const totalQueues = regionMetrics.totalQueues;

    return {
      avgSpeed:
        avgSpeeds.length > 0
          ? avgSpeeds.reduce((a, b) => a + b, 0) / avgSpeeds.length
          : latest.metricsGlobal.avgSpeed,
      totalDelay: latest.metricsGlobal.totalDelay,
      maxQueue: Math.max(...totalQueues, 0),
      numVehicles: latest.metricsGlobal.numVehicles,
    };
  }, [timeseries, regionMetrics]);

  const loading = runsLoading || timeseriesLoading;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  if (!latestRun) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
          No Simulation Data
        </h2>
        <p className="text-gray-500 dark:text-gray-400">
          Run a simulation from the Scenarios page to see data here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with region filter */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Dashboard
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Latest run: {latestRun.id} | {timeseries.length} data points
          </p>
        </div>

        <div className="w-full sm:w-48">
          <RegionFilter value={selectedRegion} onChange={setSelectedRegion} />
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          title="Average Speed"
          value={kpis.avgSpeed.toFixed(1)}
          unit="m/s"
          icon={<BoltIcon className="w-6 h-6" />}
          color="blue"
        />
        <KPICard
          title="Total Delay"
          value={kpis.totalDelay.toFixed(0)}
          unit="sec"
          icon={<ClockIcon className="w-6 h-6" />}
          color="yellow"
        />
        <KPICard
          title="Max Queue Length"
          value={kpis.maxQueue}
          unit="vehicles"
          icon={<QueueListIcon className="w-6 h-6" />}
          color="red"
        />
        <KPICard
          title="Active Vehicles"
          value={kpis.numVehicles}
          icon={<TruckIcon className="w-6 h-6" />}
          color="green"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Speed Chart */}
        <div className="card p-4">
          <SpeedChart
            times={regionMetrics.times}
            speeds={regionMetrics.avgSpeeds}
            title={`Average Speed - ${selectedRegion === 'all' ? 'All Regions' : selectedRegion}`}
            height={350}
          />
        </div>

        {/* Queue Chart */}
        <div className="card p-4">
          <QueueChart
            times={regionMetrics.times}
            queues={regionMetrics.totalQueues}
            title={`Queue Length - ${selectedRegion === 'all' ? 'All Regions' : selectedRegion}`}
            height={350}
          />
        </div>
      </div>

      {/* Run Summary */}
      {latestRun.summary && (
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Run Summary
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-gray-500 dark:text-gray-400">Overall Avg Speed</p>
              <p className="font-medium text-gray-900 dark:text-white">
                {latestRun.summary.avgSpeed.toFixed(2)} m/s
              </p>
            </div>
            <div>
              <p className="text-gray-500 dark:text-gray-400">Average Delay</p>
              <p className="font-medium text-gray-900 dark:text-white">
                {latestRun.summary.avgDelay.toFixed(2)} sec
              </p>
            </div>
            <div>
              <p className="text-gray-500 dark:text-gray-400">Max Queue</p>
              <p className="font-medium text-gray-900 dark:text-white">
                {latestRun.summary.maxQueueLength} vehicles
              </p>
            </div>
            <div>
              <p className="text-gray-500 dark:text-gray-400">Total Timesteps</p>
              <p className="font-medium text-gray-900 dark:text-white">
                {latestRun.summary.totalTimesteps}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
