/**
 * API Client for Backend Services
 */

// Use empty string for production (same origin via nginx proxy)
// or localhost:8000 for development
const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : '';

interface RunSimulationParams {
  name: string;
  description?: string;
  demandProfile: string;
  simulationDuration: number;
  accident: {
    enabled: boolean;
    edgeId: string;
    startTime: number;
    duration: number;
    severity: string;
    blockedLanes: number[];
    speedReduction: number;
  };
  roadWorks: {
    enabled: boolean;
    edgeId: string;
    startTime: number;
    duration: number;
    blockedLanes: number[];
    speedReduction: number;
  };
  useGui: boolean;  // Open SUMO-GUI visualization window
  useAdaptiveControl: boolean;  // Enable ML-based signal control
}

export async function runSimulation(params: RunSimulationParams) {
  const response = await fetch(`${API_BASE}/run-simulation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario: params }),
  });

  if (!response.ok) {
    throw new Error('Failed to start simulation');
  }

  return response.json();
}

export async function getRun(runId: string) {
  const response = await fetch(`${API_BASE}/runs/${runId}`);
  if (!response.ok) throw new Error('Failed to fetch run');
  return response.json();
}

export async function listRuns(options?: { status?: string; limit?: number }) {
  const params = new URLSearchParams();
  if (options?.status) params.append('status', options.status);
  if (options?.limit) params.append('limit', options.limit.toString());

  const response = await fetch(`${API_BASE}/runs?${params}`);
  if (!response.ok) throw new Error('Failed to fetch runs');
  return response.json();
}

export async function getTimeseries(runId: string, limit?: number) {
  const params = new URLSearchParams();
  if (limit) params.append('limit', limit.toString());

  const response = await fetch(`${API_BASE}/runs/${runId}/timeseries?${params}`);
  if (!response.ok) throw new Error('Failed to fetch timeseries');
  return response.json();
}

export async function getEdges() {
  const response = await fetch(`${API_BASE}/edges`);
  if (!response.ok) throw new Error('Failed to fetch edges');
  return response.json();
}

export async function getPrediction(
  runId: string,
  edgeId: string,
  horizon: number = 300
) {
  const response = await fetch(
    `${API_BASE}/predict/edges/${runId}/${edgeId}?horizon=${horizon}`
  );
  if (!response.ok) throw new Error('Failed to get prediction');
  return response.json();
}

export async function predictTraffic(
  edgeHistories: Array<{
    edgeId: string;
    speeds: number[];
    queueLens: number[];
    eventFlags?: boolean[];
  }>,
  horizonSeconds: number = 300,
  stepSeconds: number = 60
) {
  const response = await fetch(`${API_BASE}/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      horizonSeconds,
      stepSeconds,
      edgeHistories,
    }),
  });

  if (!response.ok) throw new Error('Failed to get predictions');
  return response.json();
}

export async function compareRuns(runIds: string[]) {
  const response = await fetch(`${API_BASE}/compare?run_ids=${runIds.join(',')}`);
  if (!response.ok) throw new Error('Failed to compare runs');
  return response.json();
}

export async function compareTimeseries(
  runIds: string[],
  metric: string = 'avgSpeed'
) {
  const response = await fetch(
    `${API_BASE}/compare/timeseries?run_ids=${runIds.join(',')}&metric=${metric}`
  );
  if (!response.ok) throw new Error('Failed to compare timeseries');
  return response.json();
}

export async function checkHealth() {
  const response = await fetch(`${API_BASE}/health`);
  return response.json();
}

export interface NetworkData {
  bounds: {
    minX: number;
    minY: number;
    maxX: number;
    maxY: number;
  };
  junctions: Array<{
    id: string;
    type: string;
    x: number;
    y: number;
    shape: string;
  }>;
  edges: Array<{
    id: string;
    from: string;
    to: string;
    region: string;
    label: string;
    lanes: Array<{
      id: string;
      speed: number;
      length: number;
      shape: Array<{ x: number; y: number }>;
    }>;
  }>;
}

export async function getNetwork(): Promise<NetworkData> {
  const response = await fetch(`${API_BASE}/network`);
  if (!response.ok) throw new Error('Failed to fetch network');
  return response.json();
}

export interface TrafficLightPhase {
  duration: number;
  state: string;
  minDur: number | null;
  maxDur: number | null;
}

export interface TrafficLight {
  id: string;
  type: string;
  phaseCount: number;
  phases: TrafficLightPhase[];
  position?: { x: number; y: number };
}

export interface SignalState {
  tlsId: string;
  phase: number;
  state: string;
  nextSwitch: number;
}

export interface LiveState {
  runId: string;
  status: string;
  simTime: number;
  timestamp: string;
  metricsGlobal: {
    numVehicles: number;
    avgSpeed: number;
    totalDelay: number;
    totalQueueLength: number;
    avgWaitingTime: number;
  };
  signalStates: SignalState[];
  vehicleCount: number;
  adaptiveControl: boolean;
  activeEvents: string[];
}

export async function getTrafficLights(): Promise<{ count: number; trafficLights: TrafficLight[] }> {
  const response = await fetch(`${API_BASE}/network/traffic-lights`);
  if (!response.ok) throw new Error('Failed to fetch traffic lights');
  return response.json();
}

export async function getLiveState(runId: string): Promise<LiveState> {
  const response = await fetch(`${API_BASE}/runs/${runId}/live-state`);
  if (!response.ok) throw new Error('Failed to fetch live state');
  return response.json();
}

export async function getSignalHistory(
  runId: string,
  tlsId?: string,
  limit: number = 100
) {
  const params = new URLSearchParams();
  if (tlsId) params.append('tls_id', tlsId);
  params.append('limit', limit.toString());

  const response = await fetch(`${API_BASE}/runs/${runId}/signal-history?${params}`);
  if (!response.ok) throw new Error('Failed to fetch signal history');
  return response.json();
}

export async function getEdgeMetricsHistory(
  runId: string,
  edgeId: string,
  limit: number = 200
) {
  const response = await fetch(`${API_BASE}/runs/${runId}/edge-metrics/${edgeId}?limit=${limit}`);
  if (!response.ok) throw new Error('Failed to fetch edge metrics');
  return response.json();
}

// ============================================================================
// CHAT API
// ============================================================================

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  message: string;
  runId?: string;
  conversationHistory: ChatMessage[];
  includeVoice: boolean;
}

export interface ChatResponse {
  response: string;
  audioUrl?: string;
  timestamp: string;
}

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) throw new Error('Failed to send chat message');
  return response.json();
}

export async function transcribeAudio(audioBlob: Blob): Promise<{ text: string }> {
  // Determine the correct file extension based on MIME type
  let filename = 'recording.webm';
  const mimeType = audioBlob.type;
  if (mimeType.includes('mp4')) {
    filename = 'recording.mp4';
  } else if (mimeType.includes('ogg')) {
    filename = 'recording.ogg';
  } else if (mimeType.includes('wav')) {
    filename = 'recording.wav';
  } else if (mimeType.includes('mp3') || mimeType.includes('mpeg')) {
    filename = 'recording.mp3';
  }

  console.log('Sending audio for transcription:', {
    mimeType,
    filename,
    size: audioBlob.size
  });

  const formData = new FormData();
  formData.append('file', audioBlob, filename);

  const response = await fetch(`${API_BASE}/chat/transcribe-upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error('Transcription API error:', response.status, errorText);
    throw new Error(`Failed to transcribe audio: ${response.status}`);
  }
  return response.json();
}

export async function textToSpeech(text: string): Promise<{ audio: string; format: string }> {
  const response = await fetch(`${API_BASE}/chat/tts-json`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) throw new Error('Failed to generate speech');
  return response.json();
}

export async function analyzeRun(runId: string): Promise<{ analysis: string; timestamp: string }> {
  const response = await fetch(`${API_BASE}/chat/analyze/${runId}`, {
    method: 'POST',
  });

  if (!response.ok) throw new Error('Failed to analyze run');
  return response.json();
}
