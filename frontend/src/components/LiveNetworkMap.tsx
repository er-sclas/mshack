/**
 * Live Network Map Component
 *
 * Real-time visualization of the SUMO road network with:
 * - Traffic light states (red/yellow/green)
 * - Vehicle positions and flow
 * - Active events (accidents, road works)
 * - ML-based adaptive control indicators
 */

import { useState, useEffect, useMemo } from 'react';
import {
  getNetwork,
  getTrafficLights,
  getLiveState,
  type NetworkData,
  type TrafficLight,
  type SignalState,
  type LiveState
} from '../utils/api';

interface LiveNetworkMapProps {
  runId?: string;
  selectedEdge?: string;
  onEdgeSelect?: (edgeId: string) => void;
  height?: number;
  refreshInterval?: number; // in milliseconds
}

// Region colors
const REGION_COLORS: Record<string, string> = {
  busy_junction: '#ef4444', // red
  university: '#8b5cf6',    // purple
  stadium: '#f97316',       // orange
  kamarajar: '#10b981',     // green
  other: '#6b7280',         // gray
};

// Signal state colors
const SIGNAL_COLORS: Record<string, string> = {
  G: '#22c55e', // green
  g: '#86efac', // green (permissive)
  y: '#eab308', // yellow
  Y: '#eab308', // yellow
  r: '#ef4444', // red
  R: '#ef4444', // red (forced)
  s: '#ef4444', // red (stop)
  o: '#22c55e', // off (blinking green)
  O: '#22c55e', // off (blinking green)
};

// Get dominant signal color for a TLS
function getDominantSignalColor(state: string): string {
  const counts: Record<string, number> = { G: 0, g: 0, y: 0, r: 0 };

  for (const char of state) {
    if (char === 'G' || char === 'g' || char === 'o' || char === 'O') counts.G++;
    else if (char === 'y' || char === 'Y') counts.y++;
    else if (char === 'r' || char === 'R' || char === 's') counts.r++;
  }

  // Priority: yellow (transitioning) > green > red
  if (counts.y > 0) return SIGNAL_COLORS.y;
  if (counts.G > counts.r) return SIGNAL_COLORS.G;
  return SIGNAL_COLORS.r;
}

export function LiveNetworkMap({
  runId,
  selectedEdge,
  onEdgeSelect,
  height = 500,
  refreshInterval = 2000
}: LiveNetworkMapProps) {
  const [network, setNetwork] = useState<NetworkData | null>(null);
  const [trafficLights, setTrafficLights] = useState<TrafficLight[]>([]);
  const [liveState, setLiveState] = useState<LiveState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch static network data
  useEffect(() => {
    Promise.all([getNetwork(), getTrafficLights()])
      .then(([networkData, tlData]) => {
        setNetwork(networkData);
        setTrafficLights(tlData.trafficLights);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load network:', err);
        setError('Failed to load network data');
        setLoading(false);
      });
  }, []);

  // Poll for live state when runId is provided
  useEffect(() => {
    if (!runId) {
      setLiveState(null);
      return;
    }

    const fetchLiveState = () => {
      getLiveState(runId)
        .then(setLiveState)
        .catch((err) => {
          console.error('Failed to fetch live state:', err);
        });
    };

    fetchLiveState();
    const interval = setInterval(fetchLiveState, refreshInterval);
    return () => clearInterval(interval);
  }, [runId, refreshInterval]);

  // Build signal state map
  const signalStateMap = useMemo(() => {
    const map: Record<string, SignalState> = {};
    if (liveState?.signalStates) {
      for (const signal of liveState.signalStates) {
        map[signal.tlsId] = signal;
      }
    }
    return map;
  }, [liveState]);

  // Transform coordinates to SVG viewport
  const transform = useMemo(() => {
    if (!network) return null;

    const { bounds } = network;
    const padding = 20;
    const width = bounds.maxX - bounds.minX;
    const netHeight = bounds.maxY - bounds.minY;

    const viewWidth = 100;
    const viewHeight = 100 * (netHeight / width);

    return {
      x: (nx: number) => ((nx - bounds.minX) / width) * (viewWidth - padding * 2) + padding,
      y: (ny: number) => viewHeight - ((ny - bounds.minY) / netHeight) * (viewHeight - padding * 2) - padding,
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

  const activeEvents = liveState?.activeEvents || [];

  return (
    <div className="relative bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden" style={{ height }}>
      {/* Status bar */}
      <div className="absolute top-2 right-2 bg-white dark:bg-gray-900 rounded-lg p-2 shadow-md z-10 text-xs">
        {runId && liveState ? (
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${
                liveState.status === 'running' ? 'bg-green-500 animate-pulse' :
                liveState.status === 'completed' ? 'bg-blue-500' : 'bg-gray-400'
              }`} />
              <span className="font-medium text-gray-700 dark:text-gray-300">
                {liveState.status === 'running' ? 'Live' : liveState.status}
              </span>
            </div>
            <div className="text-gray-500 dark:text-gray-400">
              Time: {Math.floor(liveState.simTime / 60)}m {Math.floor(liveState.simTime % 60)}s
            </div>
            <div className="text-gray-500 dark:text-gray-400">
              Vehicles: {liveState.vehicleCount}
            </div>
            {liveState.adaptiveControl && (
              <div className="text-green-600 dark:text-green-400 font-medium">
                ML Control Active
              </div>
            )}
          </div>
        ) : (
          <div className="text-gray-500 dark:text-gray-400">
            No simulation selected
          </div>
        )}
      </div>

      {/* Traffic Light Legend */}
      <div className="absolute top-2 left-2 bg-white dark:bg-gray-900 rounded-lg p-2 shadow-md z-10">
        <div className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">Traffic Signals</div>
        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-full bg-green-500" />
            <span className="text-gray-500">Green</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-full bg-yellow-500" />
            <span className="text-gray-500">Yellow</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-full bg-red-500" />
            <span className="text-gray-500">Red</span>
          </div>
        </div>
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
          const hasEvent = activeEvents.includes(edge.id);
          const color = hasEvent ? '#dc2626' : REGION_COLORS[edge.region] || REGION_COLORS.other;

          const lane = edge.lanes[0];
          if (!lane || lane.shape.length < 2) return null;

          const pathD = lane.shape.map((point, i) => {
            const x = transform.x(point.x);
            const y = transform.y(point.y);
            return i === 0 ? `M ${x} ${y}` : `L ${x} ${y}`;
          }).join(' ');

          return (
            <g key={edge.id}>
              {/* Event highlight */}
              {hasEvent && (
                <path
                  d={pathD}
                  stroke="#fbbf24"
                  strokeWidth={3}
                  strokeOpacity={0.5}
                  fill="none"
                  className="animate-pulse"
                />
              )}
              {/* Road line */}
              <path
                d={pathD}
                stroke={color}
                strokeWidth={isSelected ? 1.5 : 0.8}
                strokeOpacity={isSelected ? 1 : hasEvent ? 0.9 : 0.6}
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="cursor-pointer transition-all hover:stroke-opacity-100"
                onClick={() => onEdgeSelect?.(edge.id)}
              />
              {/* Clickable area */}
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

        {/* Draw traffic lights */}
        {trafficLights.map((tl) => {
          if (!tl.position) return null;

          const x = transform.x(tl.position.x);
          const y = transform.y(tl.position.y);

          // Get current signal state
          const signalState = signalStateMap[tl.id];
          const signalColor = signalState
            ? getDominantSignalColor(signalState.state)
            : '#374151';

          return (
            <g key={tl.id}>
              {/* Outer glow for active signals */}
              {signalState && (
                <circle
                  cx={x}
                  cy={y}
                  r={2.5}
                  fill={signalColor}
                  fillOpacity={0.3}
                  className={signalState ? 'animate-pulse' : ''}
                />
              )}
              {/* Signal circle */}
              <circle
                cx={x}
                cy={y}
                r={1.5}
                fill={signalColor}
                stroke="#374151"
                strokeWidth={0.3}
              >
                <title>
                  {tl.id}
                  {signalState ? `\nPhase: ${signalState.phase}\nNext switch: ${signalState.nextSwitch.toFixed(0)}s` : ''}
                </title>
              </circle>
            </g>
          );
        })}

        {/* Draw regular junctions */}
        {network.junctions
          .filter(j => j.type !== 'traffic_light')
          .map((junction) => {
            if (junction.id.startsWith(':')) return null;

            const x = transform.x(junction.x);
            const y = transform.y(junction.y);

            return (
              <circle
                key={junction.id}
                cx={x}
                cy={y}
                r={0.6}
                fill="#374151"
                className="dark:fill-gray-500"
              />
            );
          })}

        {/* Traffic light labels */}
        {trafficLights
          .filter(tl => tl.position)
          .map((tl) => {
            if (!tl.position) return null;

            const x = transform.x(tl.position.x);
            const y = transform.y(tl.position.y);

            const label = tl.id
              .replace('junction_', '')
              .replace('_', ' ')
              .toUpperCase();

            return (
              <text
                key={`label-${tl.id}`}
                x={x}
                y={y + 4}
                textAnchor="middle"
                className="text-[2px] fill-gray-600 dark:fill-gray-400 font-medium"
              >
                {label}
              </text>
            );
          })}
      </svg>

      {/* Active events indicator */}
      {activeEvents.length > 0 && (
        <div className="absolute bottom-2 left-2 bg-red-100 dark:bg-red-900/50 rounded-lg p-2 shadow-md">
          <div className="text-xs font-semibold text-red-700 dark:text-red-300 flex items-center gap-1">
            <span className="animate-pulse">!</span>
            {activeEvents.length} Active Event{activeEvents.length > 1 ? 's' : ''}
          </div>
        </div>
      )}

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

export default LiveNetworkMap;
