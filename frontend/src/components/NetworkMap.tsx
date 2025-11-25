/**
 * Network Map Component
 *
 * SVG-based visualization of the SUMO road network.
 * Fetches actual network geometry from the backend API.
 */

import { useState, useEffect, useMemo } from 'react';
import { getNetwork, type NetworkData } from '../utils/api';

interface NetworkMapProps {
  selectedEdge?: string;
  onEdgeSelect?: (edgeId: string) => void;
  highlightRegion?: string;
  height?: number;
}

// Region colors
const REGION_COLORS: Record<string, string> = {
  busy_junction: '#ef4444', // red
  university: '#8b5cf6',    // purple
  stadium: '#f97316',       // orange
  kamarajar: '#10b981',     // green
  other: '#6b7280',         // gray
};

const REGION_LABELS: Record<string, string> = {
  busy_junction: 'Busy Junction',
  university: 'University of Madras',
  stadium: 'MA Chidambaram Stadium',
  kamarajar: 'Kamarajar Salai',
  other: 'Other Roads',
};

export function NetworkMap({
  selectedEdge,
  onEdgeSelect,
  highlightRegion,
  height = 400
}: NetworkMapProps) {
  const [network, setNetwork] = useState<NetworkData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch network data
  useEffect(() => {
    getNetwork()
      .then((data) => {
        setNetwork(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load network:', err);
        setError('Failed to load network data');
        setLoading(false);
      });
  }, []);

  // Transform coordinates to SVG viewport
  const transform = useMemo(() => {
    if (!network) return null;

    const { bounds } = network;
    const padding = 20;
    const width = bounds.maxX - bounds.minX;
    const height = bounds.maxY - bounds.minY;

    // SVG viewBox dimensions
    const viewWidth = 100;
    const viewHeight = 100 * (height / width);

    return {
      // Transform network coordinates to SVG coordinates
      x: (nx: number) => ((nx - bounds.minX) / width) * (viewWidth - padding * 2) + padding,
      // Flip Y axis (SVG y increases downward, SUMO y increases upward)
      y: (ny: number) => viewHeight - ((ny - bounds.minY) / height) * (viewHeight - padding * 2) - padding,
      viewBox: `0 0 ${viewWidth} ${viewHeight}`,
      viewWidth,
      viewHeight,
    };
  }, [network]);

  if (loading) {
    return (
      <div
        className="flex items-center justify-center bg-gray-100 dark:bg-gray-800 rounded-lg"
        style={{ height }}
      >
        <div className="text-gray-500 dark:text-gray-400">Loading network...</div>
      </div>
    );
  }

  if (error || !network || !transform) {
    return (
      <div
        className="flex items-center justify-center bg-gray-100 dark:bg-gray-800 rounded-lg"
        style={{ height }}
      >
        <div className="text-red-500">{error || 'Failed to load network'}</div>
      </div>
    );
  }

  return (
    <div className="relative bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden" style={{ height }}>
      {/* Legend */}
      <div className="absolute top-2 left-2 bg-white dark:bg-gray-900 rounded-lg p-2 shadow-md z-10">
        <div className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">Regions</div>
        {Object.entries(REGION_LABELS).filter(([k]) => k !== 'other').map(([region, label]) => (
          <div
            key={region}
            className={`flex items-center gap-2 text-xs py-0.5 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 px-1 rounded ${
              highlightRegion === region ? 'bg-gray-200 dark:bg-gray-700' : ''
            }`}
          >
            <div
              className="w-3 h-3 rounded-sm"
              style={{ backgroundColor: REGION_COLORS[region] }}
            />
            <span className="text-gray-600 dark:text-gray-400">{label}</span>
          </div>
        ))}
      </div>

      {/* SVG Network */}
      <svg
        viewBox={transform.viewBox}
        className="w-full h-full"
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Background */}
        <rect width={transform.viewWidth} height={transform.viewHeight} fill="#f3f4f6" className="dark:fill-gray-800" />

        {/* Draw edges (roads) */}
        {network.edges.map((edge) => {
          const isSelected = selectedEdge === edge.id;
          const isHighlighted = highlightRegion === edge.region;
          const color = REGION_COLORS[edge.region] || REGION_COLORS.other;

          // Use the first lane's shape for drawing
          const lane = edge.lanes[0];
          if (!lane || lane.shape.length < 2) return null;

          // Create path from lane shape
          const pathD = lane.shape.map((point, i) => {
            const x = transform.x(point.x);
            const y = transform.y(point.y);
            return i === 0 ? `M ${x} ${y}` : `L ${x} ${y}`;
          }).join(' ');

          return (
            <g key={edge.id}>
              {/* Road line */}
              <path
                d={pathD}
                stroke={color}
                strokeWidth={isSelected ? 1.5 : isHighlighted ? 1.2 : 0.8}
                strokeOpacity={isSelected ? 1 : isHighlighted ? 0.9 : 0.6}
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="cursor-pointer transition-all"
                onClick={() => onEdgeSelect?.(edge.id)}
              />
              {/* Larger clickable area */}
              <path
                d={pathD}
                stroke="transparent"
                strokeWidth={3}
                fill="none"
                className="cursor-pointer"
                onClick={() => onEdgeSelect?.(edge.id)}
              >
                <title>{edge.label}</title>
              </path>
            </g>
          );
        })}

        {/* Draw junctions (nodes) */}
        {network.junctions.map((junction) => {
          // Skip internal junctions or those without coordinates
          if (junction.id.startsWith(':')) return null;

          const x = transform.x(junction.x);
          const y = transform.y(junction.y);

          // Different styles for different junction types
          const isTrafficLight = junction.type === 'traffic_light';

          return (
            <circle
              key={junction.id}
              cx={x}
              cy={y}
              r={isTrafficLight ? 1.2 : 0.8}
              fill={isTrafficLight ? '#fbbf24' : '#374151'}
              className="dark:fill-gray-400"
            >
              <title>{junction.id}</title>
            </circle>
          );
        })}

        {/* Labels for major junctions */}
        {network.junctions
          .filter(j => j.type === 'traffic_light' && !j.id.startsWith(':'))
          .map((junction) => {
            const x = transform.x(junction.x);
            const y = transform.y(junction.y);

            // Shorten junction names for display
            const label = junction.id
              .replace('junction_', '')
              .replace('_', ' ')
              .toUpperCase();

            return (
              <text
                key={`label-${junction.id}`}
                x={x}
                y={y + 3}
                textAnchor="middle"
                className="text-[2px] fill-gray-600 dark:fill-gray-400 font-medium"
              >
                {label}
              </text>
            );
          })}
      </svg>

      {/* Selected edge info */}
      {selectedEdge && (
        <div className="absolute bottom-2 right-2 bg-white dark:bg-gray-900 rounded-lg p-2 shadow-md">
          <div className="text-xs font-medium text-gray-900 dark:text-white">
            Selected: {network.edges.find(e => e.id === selectedEdge)?.label || selectedEdge}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            ID: {selectedEdge}
          </div>
        </div>
      )}
    </div>
  );
}

export default NetworkMap;
