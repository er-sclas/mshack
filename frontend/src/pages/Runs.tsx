/**
 * Runs List Page
 *
 * List of all simulation runs with status and quick actions.
 */

import { Link } from 'react-router-dom';
import { useRuns } from '../hooks/useFirestore';
import {
  CheckCircleIcon,
  ClockIcon,
  ExclamationCircleIcon,
  PlayIcon,
} from '@heroicons/react/24/outline';
import { clsx } from 'clsx';

const statusConfig = {
  completed: {
    icon: CheckCircleIcon,
    color: 'text-green-500',
    bg: 'bg-green-100 dark:bg-green-900/30',
    label: 'Completed',
  },
  running: {
    icon: PlayIcon,
    color: 'text-yellow-500',
    bg: 'bg-yellow-100 dark:bg-yellow-900/30',
    label: 'Running',
  },
  pending: {
    icon: ClockIcon,
    color: 'text-blue-500',
    bg: 'bg-blue-100 dark:bg-blue-900/30',
    label: 'Pending',
  },
  failed: {
    icon: ExclamationCircleIcon,
    color: 'text-red-500',
    bg: 'bg-red-100 dark:bg-red-900/30',
    label: 'Failed',
  },
};

export default function Runs() {
  const { runs, loading, error } = useRuns({ maxResults: 50 });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <ExclamationCircleIcon className="w-12 h-12 text-red-500 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
          Error Loading Runs
        </h2>
        <p className="text-gray-500 dark:text-gray-400">{error.message}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Simulation Runs
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {runs.length} runs found
          </p>
        </div>
        <Link to="/scenarios" className="btn-primary">
          New Simulation
        </Link>
      </div>

      {/* Runs list */}
      {runs.length === 0 ? (
        <div className="text-center py-12 card">
          <ClockIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            No Runs Yet
          </h3>
          <p className="text-gray-500 dark:text-gray-400 mb-4">
            Create your first simulation scenario to get started.
          </p>
          <Link to="/scenarios" className="btn-primary">
            Create Scenario
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {runs.map((run) => {
            const status = statusConfig[run.status] || statusConfig.pending;
            const StatusIcon = status.icon;

            return (
              <Link
                key={run.id}
                to={`/runs/${run.id}`}
                className="card p-4 block hover:shadow-md transition-shadow"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    {/* Status icon */}
                    <div className={clsx('p-2 rounded-lg', status.bg)}>
                      <StatusIcon className={clsx('w-5 h-5', status.color)} />
                    </div>

                    {/* Run info */}
                    <div>
                      <p className="font-medium text-gray-900 dark:text-white">
                        Run: {run.id}
                      </p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        Scenario: {run.scenarioId}
                      </p>
                    </div>
                  </div>

                  {/* Right side info */}
                  <div className="text-right">
                    <span
                      className={clsx(
                        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                        status.bg,
                        status.color
                      )}
                    >
                      {status.label}
                    </span>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                      {run.createdAt
                        ? new Date(run.createdAt).toLocaleString()
                        : 'Unknown'}
                    </p>
                  </div>
                </div>

                {/* Summary stats if available */}
                {run.summary && run.status === 'completed' && (
                  <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
                    <div className="grid grid-cols-4 gap-4 text-sm">
                      <div>
                        <p className="text-gray-500 dark:text-gray-400">Avg Speed</p>
                        <p className="font-medium text-gray-900 dark:text-white">
                          {run.summary.avgSpeed.toFixed(1)} m/s
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-500 dark:text-gray-400">Avg Delay</p>
                        <p className="font-medium text-gray-900 dark:text-white">
                          {run.summary.avgDelay.toFixed(1)} s
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-500 dark:text-gray-400">Max Queue</p>
                        <p className="font-medium text-gray-900 dark:text-white">
                          {run.summary.maxQueueLength}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-500 dark:text-gray-400">Timesteps</p>
                        <p className="font-medium text-gray-900 dark:text-white">
                          {run.summary.totalTimesteps}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
