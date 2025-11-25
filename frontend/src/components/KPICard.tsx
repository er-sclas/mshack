/**
 * KPI Card Component
 *
 * Displays a single metric with optional trend indicator.
 */

import { clsx } from 'clsx';
import { ArrowUpIcon, ArrowDownIcon } from '@heroicons/react/24/solid';

interface KPICardProps {
  title: string;
  value: string | number;
  unit?: string;
  trend?: number;
  trendLabel?: string;
  icon?: React.ReactNode;
  color?: 'blue' | 'green' | 'red' | 'yellow' | 'purple';
}

const colorClasses = {
  blue: 'bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
  green: 'bg-green-50 text-green-600 dark:bg-green-900/30 dark:text-green-400',
  red: 'bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400',
  yellow: 'bg-yellow-50 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400',
  purple: 'bg-purple-50 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400',
};

export default function KPICard({
  title,
  value,
  unit,
  trend,
  trendLabel,
  icon,
  color = 'blue',
}: KPICardProps) {
  const isPositiveTrend = trend !== undefined && trend > 0;
  const isNegativeTrend = trend !== undefined && trend < 0;

  return (
    <div className="card p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
            {title}
          </p>
          <div className="mt-2 flex items-baseline">
            <p className="text-3xl font-semibold text-gray-900 dark:text-white">
              {typeof value === 'number' ? value.toLocaleString() : value}
            </p>
            {unit && (
              <span className="ml-1 text-sm text-gray-500 dark:text-gray-400">
                {unit}
              </span>
            )}
          </div>

          {trend !== undefined && (
            <div className="mt-2 flex items-center text-sm">
              {isPositiveTrend && (
                <ArrowUpIcon className="w-4 h-4 text-green-500 mr-1" />
              )}
              {isNegativeTrend && (
                <ArrowDownIcon className="w-4 h-4 text-red-500 mr-1" />
              )}
              <span
                className={clsx(
                  isPositiveTrend && 'text-green-600 dark:text-green-400',
                  isNegativeTrend && 'text-red-600 dark:text-red-400',
                  !isPositiveTrend && !isNegativeTrend && 'text-gray-500'
                )}
              >
                {Math.abs(trend).toFixed(1)}%
              </span>
              {trendLabel && (
                <span className="ml-1 text-gray-500 dark:text-gray-400">
                  {trendLabel}
                </span>
              )}
            </div>
          )}
        </div>

        {icon && (
          <div className={clsx('p-3 rounded-lg', colorClasses[color])}>
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}
