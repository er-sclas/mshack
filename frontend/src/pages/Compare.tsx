/**
 * Compare Page
 *
 * Compare multiple simulation runs side by side.
 */

import { useState, useEffect, useMemo } from 'react';
import { useRuns } from '../hooks/useFirestore';
import { compareTimeseries } from '../utils/api';
import { ComparisonChart, RadarChart } from '../components/Charts';
import { CheckIcon } from '@heroicons/react/24/solid';
import { clsx } from 'clsx';

export default function Compare() {
  const { runs, loading: runsLoading } = useRuns({ status: 'completed', maxResults: 20 });
  const [selectedRuns, setSelectedRuns] = useState<string[]>([]);
  const [metric, setMetric] = useState<'avgSpeed' | 'totalDelay' | 'totalQueueLength'>('avgSpeed');
  const [comparisonData, setComparisonData] = useState<Record<string, Array<{ t: number; value: number }>>>({});
  const [loadingComparison, setLoadingComparison] = useState(false);

  // Toggle run selection
  const toggleRun = (runId: string) => {
    setSelectedRuns((prev) => {
      if (prev.includes(runId)) {
        return prev.filter((id) => id !== runId);
      }
      if (prev.length >= 5) {
        return prev; // Max 5 runs
      }
      return [...prev, runId];
    });
  };

  // Fetch comparison data when selection changes
  useEffect(() => {
    if (selectedRuns.length < 2) {
      setComparisonData({});
      return;
    }

    setLoadingComparison(true);
    compareTimeseries(selectedRuns, metric)
      .then((data) => {
        setComparisonData(data.series || {});
      })
      .catch((err) => {
        console.error('Failed to fetch comparison:', err);
        setComparisonData({});
      })
      .finally(() => setLoadingComparison(false));
  }, [selectedRuns, metric]);

  // Prepare chart series
  const chartSeries = useMemo(() => {
    return Object.entries(comparisonData).map(([runId, data]) => ({
      name: `Run ${runId}`,
      data,
    }));
  }, [comparisonData]);

  // Prepare radar data
  const radarData = useMemo(() => {
    return selectedRuns
      .map((runId) => {
        const run = runs.find((r) => r.id === runId);
        if (!run?.summary) return null;
        return {
          name: `Run ${runId}`,
          avgSpeed: run.summary.avgSpeed,
          avgDelay: run.summary.avgDelay,
          maxQueueLength: run.summary.maxQueueLength,
        };
      })
      .filter(Boolean) as Array<{
      name: string;
      avgSpeed: number;
      avgDelay: number;
      maxQueueLength: number;
    }>;
  }, [selectedRuns, runs]);

  const metricLabels = {
    avgSpeed: 'Average Speed (m/s)',
    totalDelay: 'Total Delay (s)',
    totalQueueLength: 'Queue Length (vehicles)',
  };

  if (runsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
          Compare Runs
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Select 2-5 completed runs to compare their performance.
        </p>
      </div>

      {/* Run Selection */}
      <div className="card p-6">
        <h3 className="font-semibold text-gray-900 dark:text-white mb-4">
          Select Runs ({selectedRuns.length}/5)
        </h3>

        {runs.length === 0 ? (
          <p className="text-gray-500">No completed runs available for comparison.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {runs.map((run) => {
              const isSelected = selectedRuns.includes(run.id);
              return (
                <button
                  key={run.id}
                  onClick={() => toggleRun(run.id)}
                  disabled={!isSelected && selectedRuns.length >= 5}
                  className={clsx(
                    'relative p-4 rounded-lg border-2 text-left transition-all',
                    isSelected
                      ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30'
                      : 'border-gray-200 dark:border-gray-600 hover:border-gray-300',
                    !isSelected && selectedRuns.length >= 5 && 'opacity-50 cursor-not-allowed'
                  )}
                >
                  {isSelected && (
                    <CheckIcon className="absolute top-2 right-2 w-5 h-5 text-primary-600" />
                  )}
                  <p className="font-medium text-gray-900 dark:text-white">
                    Run {run.id}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {run.createdAt ? new Date(run.createdAt).toLocaleDateString() : ''}
                  </p>
                  {run.summary && (
                    <p className="text-xs text-gray-400 mt-1">
                      Avg Speed: {run.summary.avgSpeed.toFixed(1)} m/s
                    </p>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Comparison Charts */}
      {selectedRuns.length >= 2 && (
        <>
          {/* Metric selector */}
          <div className="card p-4">
            <div className="flex flex-wrap items-center gap-4">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Metric:
              </span>
              {(Object.keys(metricLabels) as Array<keyof typeof metricLabels>).map((m) => (
                <button
                  key={m}
                  onClick={() => setMetric(m)}
                  className={clsx(
                    'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                    metric === m
                      ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/50 dark:text-primary-300'
                      : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300 hover:bg-gray-200'
                  )}
                >
                  {metricLabels[m]}
                </button>
              ))}
            </div>
          </div>

          {/* Time series comparison */}
          <div className="card p-4">
            {loadingComparison ? (
              <div className="h-64 flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
              </div>
            ) : chartSeries.length > 0 ? (
              <ComparisonChart
                series={chartSeries}
                title={`${metricLabels[metric]} Over Time`}
                yAxisName={metricLabels[metric]}
                height={400}
              />
            ) : (
              <div className="h-64 flex items-center justify-center text-gray-500">
                No comparison data available
              </div>
            )}
          </div>

          {/* Radar chart */}
          <div className="card p-4">
            {radarData.length > 0 ? (
              <RadarChart
                runs={radarData}
                title="KPI Comparison (Higher is Better)"
                height={400}
              />
            ) : (
              <div className="h-64 flex items-center justify-center text-gray-500">
                No summary data available for radar chart
              </div>
            )}
          </div>

          {/* Summary table */}
          <div className="card p-6">
            <h3 className="font-semibold text-gray-900 dark:text-white mb-4">
              Summary Comparison
            </h3>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead>
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Run
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Avg Speed
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Avg Delay
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Max Queue
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Timesteps
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                  {selectedRuns.map((runId) => {
                    const run = runs.find((r) => r.id === runId);
                    return (
                      <tr key={runId}>
                        <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                          {runId}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                          {run?.summary?.avgSpeed.toFixed(2) || '-'} m/s
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                          {run?.summary?.avgDelay.toFixed(2) || '-'} s
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                          {run?.summary?.maxQueueLength || '-'}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                          {run?.summary?.totalTimesteps || '-'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {selectedRuns.length < 2 && selectedRuns.length > 0 && (
        <div className="card p-8 text-center">
          <p className="text-gray-500 dark:text-gray-400">
            Select at least one more run to start comparing.
          </p>
        </div>
      )}

      {selectedRuns.length === 0 && runs.length > 0 && (
        <div className="card p-8 text-center">
          <p className="text-gray-500 dark:text-gray-400">
            Select runs from the list above to compare their performance metrics.
          </p>
        </div>
      )}
    </div>
  );
}
