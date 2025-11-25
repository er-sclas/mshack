// Type definitions for Chepauk Traffic Portal

export interface GlobalMetrics {
  numVehicles: number;
  avgSpeed: number;
  totalDelay: number;
  totalQueueLength: number;
  avgWaitingTime: number;
}

export interface EdgeMetrics {
  edgeId: string;
  avgSpeed: number;
  flow: number;
  queueLen: number;
  occupancy: number;
  waitingTime: number;
  regionTag: string;
  accidentFlag: boolean;
  workzoneFlag: boolean;
}

export interface TimeseriesPoint {
  id: string;
  t: number;
  timestamp: string;
  metricsGlobal: GlobalMetrics;
  metricsByEdge: EdgeMetrics[];
}

export interface RunSummary {
  avgSpeed: number;
  maxDelay: number;
  avgDelay: number;
  maxQueueLength: number;
  avgQueueLength: number;
  totalTimesteps: number;
  adaptiveControl?: boolean;
  mlModel?: string;
}

export interface Run {
  id: string;
  scenarioId: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  startedAt: string | null;
  completedAt: string | null;
  summary: RunSummary | null;
  createdAt: string;
}

export interface ScenarioParameters {
  name: string;
  description: string;
  demandProfile: string;
  simulationDuration: number;
  accident: AccidentConfig;
  roadWorks: RoadWorksConfig;
}

export interface Scenario {
  id: string;
  name: string;
  description: string;
  parameters: ScenarioParameters;
  createdAt: string;
}

export interface AccidentConfig {
  enabled: boolean;
  edgeId: string;
  startTime: number;
  duration: number;
  severity: 'minor' | 'moderate' | 'major';
  blockedLanes: number[];
  speedReduction: number;
}

export interface RoadWorksConfig {
  enabled: boolean;
  edgeId: string;
  startTime: number;
  duration: number;
  blockedLanes: number[];
  speedReduction: number;
}

export interface EdgeInfo {
  edgeId: string;
  label: string;
  region: string;
}

export interface Prediction {
  edgeId: string;
  t: number;
  speed: number;
  queueLen: number;
}

export type Region = 'all' | 'university' | 'stadium' | 'busy_junction';

export interface ChartDataPoint {
  time: number;
  value: number;
  label?: string;
}
