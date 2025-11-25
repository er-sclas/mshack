/**
 * Scenarios Page
 *
 * Form to create and run new simulation scenarios.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { runSimulation, getEdges } from '../utils/api';
import type { EdgeInfo } from '../types';
import { LiveNetworkMap } from '../components/LiveNetworkMap';

interface FormData {
  name: string;
  description: string;
  demandProfile: 'normal_day' | 'match_day' | 'exam_day';
  simulationDuration: number;
  accidentEnabled: boolean;
  accidentEdge: string;
  accidentStartTime: number;
  accidentDuration: number;
  accidentSeverity: 'minor' | 'moderate' | 'major';
  roadWorksEnabled: boolean;
  roadWorksEdge: string;
  roadWorksStartTime: number;
  roadWorksDuration: number;
  useGui: boolean;  // Open SUMO-GUI window
  useAdaptiveControl: boolean;  // Enable ML control
}

const demandProfiles = [
  { value: 'normal_day', label: 'Normal Day', description: 'Regular university and through traffic' },
  { value: 'match_day', label: 'Match Day', description: 'High stadium traffic with pre/post match surges' },
  { value: 'exam_day', label: 'Exam Day', description: 'Elevated university traffic' },
];

const severities = [
  { value: 'minor', label: 'Minor', description: 'One lane blocked, 50% speed reduction' },
  { value: 'moderate', label: 'Moderate', description: 'One lane blocked, 70% speed reduction' },
  { value: 'major', label: 'Major', description: 'Multiple lanes blocked, 80% speed reduction' },
];

export default function Scenarios() {
  const navigate = useNavigate();
  const [edges, setEdges] = useState<EdgeInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState<FormData>({
    name: '',
    description: '',
    demandProfile: 'normal_day',
    simulationDuration: 3600,
    accidentEnabled: false,
    accidentEdge: '',
    accidentStartTime: 1800,
    accidentDuration: 900,
    accidentSeverity: 'moderate',
    roadWorksEnabled: false,
    roadWorksEdge: '',
    roadWorksStartTime: 0,
    roadWorksDuration: 3600,
    useGui: true,  // Default to opening SUMO-GUI
    useAdaptiveControl: true,  // Default to ML control
  });

  // Load available edges
  useEffect(() => {
    getEdges()
      .then((data) => setEdges(data.edges))
      .catch((err) => console.error('Failed to load edges:', err));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const result = await runSimulation({
        name: formData.name || `${formData.demandProfile} scenario`,
        description: formData.description,
        demandProfile: formData.demandProfile,
        simulationDuration: formData.simulationDuration,
        accident: {
          enabled: formData.accidentEnabled,
          edgeId: formData.accidentEdge,
          startTime: formData.accidentStartTime,
          duration: formData.accidentDuration,
          severity: formData.accidentSeverity,
          blockedLanes: formData.accidentSeverity === 'major' ? [0, 1] : [0],
          speedReduction:
            formData.accidentSeverity === 'major'
              ? 0.2
              : formData.accidentSeverity === 'moderate'
              ? 0.3
              : 0.5,
        },
        roadWorks: {
          enabled: formData.roadWorksEnabled,
          edgeId: formData.roadWorksEdge,
          startTime: formData.roadWorksStartTime,
          duration: formData.roadWorksDuration,
          blockedLanes: [0],
          speedReduction: 0.3,
        },
        useGui: formData.useGui,
        useAdaptiveControl: formData.useAdaptiveControl,
      });

      // Navigate to run detail page
      navigate(`/runs/${result.runId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start simulation');
    } finally {
      setLoading(false);
    }
  };

  const updateField = <K extends keyof FormData>(field: K, value: FormData[K]) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  // Group edges by region
  const edgesByRegion: Record<string, EdgeInfo[]> = {};
  edges.forEach((edge) => {
    if (!edgesByRegion[edge.region]) {
      edgesByRegion[edge.region] = [];
    }
    edgesByRegion[edge.region].push(edge);
  });

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
          Create Scenario
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Configure and run a new traffic simulation for the Chepauk area.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Network Map */}
        <div className="lg:col-span-2">
          <div className="card p-4">
            <h3 className="font-semibold text-gray-900 dark:text-white mb-3">
              Chepauk Road Network
            </h3>
            <LiveNetworkMap
              selectedEdge={formData.accidentEnabled ? formData.accidentEdge : formData.roadWorksEdge}
              onEdgeSelect={(edgeId) => {
                if (formData.accidentEnabled) {
                  updateField('accidentEdge', edgeId);
                } else if (formData.roadWorksEnabled) {
                  updateField('roadWorksEdge', edgeId);
                }
              }}
              height={350}
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
              Click on a road segment to select it for accident or road works events.
            </p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="lg:col-span-2 space-y-6">
          {/* Basic Info */}
          <div className="card p-6 space-y-4">
            <h3 className="font-semibold text-gray-900 dark:text-white">Basic Information</h3>

            <div>
              <label className="label mb-1">Scenario Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => updateField('name', e.target.value)}
                placeholder="e.g., Match Day Rush Hour Test"
                className="input"
              />
            </div>

            <div>
              <label className="label mb-1">Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => updateField('description', e.target.value)}
                placeholder="Optional description of the scenario..."
                rows={2}
                className="input"
              />
            </div>

            <div>
              <label className="label mb-2">Demand Profile</label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {demandProfiles.map((profile) => (
                  <label
                    key={profile.value}
                    className={`relative flex cursor-pointer rounded-lg border p-4 focus:outline-none ${
                      formData.demandProfile === profile.value
                        ? 'border-primary-500 ring-2 ring-primary-500 bg-primary-50 dark:bg-primary-900/30'
                        : 'border-gray-200 dark:border-gray-600'
                    }`}
                  >
                    <input
                      type="radio"
                      name="demandProfile"
                      value={profile.value}
                      checked={formData.demandProfile === profile.value}
                      onChange={(e) =>
                        updateField('demandProfile', e.target.value as FormData['demandProfile'])
                      }
                      className="sr-only"
                    />
                    <div>
                      <span className="block text-sm font-medium text-gray-900 dark:text-white">
                        {profile.label}
                      </span>
                      <span className="block text-xs text-gray-500 dark:text-gray-400 mt-1">
                        {profile.description}
                      </span>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="label mb-1">Simulation Duration (seconds)</label>
              <input
                type="number"
                value={formData.simulationDuration}
                onChange={(e) => updateField('simulationDuration', parseInt(e.target.value) || 3600)}
                min={600}
                max={86400}
                className="input w-48"
              />
              <p className="text-xs text-gray-500 mt-1">
                {Math.floor(formData.simulationDuration / 3600)}h{' '}
                {Math.floor((formData.simulationDuration % 3600) / 60)}m
              </p>
            </div>
          </div>

          {/* Accident Configuration */}
          <div className="card p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900 dark:text-white">Accident Event</h3>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.accidentEnabled}
                  onChange={(e) => updateField('accidentEnabled', e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary-600"></div>
              </label>
            </div>

            {formData.accidentEnabled && (
              <div className="space-y-4 pt-2">
                <div>
                  <label className="label mb-1">Location (Edge)</label>
                  <select
                    value={formData.accidentEdge}
                    onChange={(e) => updateField('accidentEdge', e.target.value)}
                    className="input"
                  >
                    <option value="">Select a road...</option>
                    {Object.entries(edgesByRegion).map(([region, regionEdges]) => (
                      <optgroup key={region} label={region.toUpperCase()}>
                        {regionEdges.map((edge) => (
                          <option key={edge.edgeId} value={edge.edgeId}>
                            {edge.label}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="label mb-1">Start Time (seconds)</label>
                    <input
                      type="number"
                      value={formData.accidentStartTime}
                      onChange={(e) =>
                        updateField('accidentStartTime', parseInt(e.target.value) || 0)
                      }
                      min={0}
                      className="input"
                    />
                  </div>
                  <div>
                    <label className="label mb-1">Duration (seconds)</label>
                    <input
                      type="number"
                      value={formData.accidentDuration}
                      onChange={(e) =>
                        updateField('accidentDuration', parseInt(e.target.value) || 0)
                      }
                      min={60}
                      className="input"
                    />
                  </div>
                </div>

                <div>
                  <label className="label mb-2">Severity</label>
                  <div className="grid grid-cols-3 gap-3">
                    {severities.map((sev) => (
                      <label
                        key={sev.value}
                        className={`relative flex cursor-pointer rounded-lg border p-3 focus:outline-none ${
                          formData.accidentSeverity === sev.value
                            ? 'border-red-500 ring-2 ring-red-500 bg-red-50 dark:bg-red-900/30'
                            : 'border-gray-200 dark:border-gray-600'
                        }`}
                      >
                        <input
                          type="radio"
                          name="accidentSeverity"
                          value={sev.value}
                          checked={formData.accidentSeverity === sev.value}
                          onChange={(e) =>
                            updateField(
                              'accidentSeverity',
                              e.target.value as FormData['accidentSeverity']
                            )
                          }
                          className="sr-only"
                        />
                        <div>
                          <span className="block text-sm font-medium text-gray-900 dark:text-white">
                            {sev.label}
                          </span>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Road Works Configuration */}
          <div className="card p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900 dark:text-white">Road Works</h3>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.roadWorksEnabled}
                  onChange={(e) => updateField('roadWorksEnabled', e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary-600"></div>
              </label>
            </div>

            {formData.roadWorksEnabled && (
              <div className="space-y-4 pt-2">
                <div>
                  <label className="label mb-1">Location (Edge)</label>
                  <select
                    value={formData.roadWorksEdge}
                    onChange={(e) => updateField('roadWorksEdge', e.target.value)}
                    className="input"
                  >
                    <option value="">Select a road...</option>
                    {Object.entries(edgesByRegion).map(([region, regionEdges]) => (
                      <optgroup key={region} label={region.toUpperCase()}>
                        {regionEdges.map((edge) => (
                          <option key={edge.edgeId} value={edge.edgeId}>
                            {edge.label}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="label mb-1">Start Time (seconds)</label>
                    <input
                      type="number"
                      value={formData.roadWorksStartTime}
                      onChange={(e) =>
                        updateField('roadWorksStartTime', parseInt(e.target.value) || 0)
                      }
                      min={0}
                      className="input"
                    />
                  </div>
                  <div>
                    <label className="label mb-1">Duration (seconds)</label>
                    <input
                      type="number"
                      value={formData.roadWorksDuration}
                      onChange={(e) =>
                        updateField('roadWorksDuration', parseInt(e.target.value) || 0)
                      }
                      min={60}
                      className="input"
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Simulation Options */}
          <div className="card p-6 space-y-4">
            <h3 className="font-semibold text-gray-900 dark:text-white">Simulation Options</h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              {/* Open SUMO-GUI Toggle */}
              <div className="flex items-start gap-4">
                <div className="flex items-center h-6">
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.useGui}
                      onChange={(e) => updateField('useGui', e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary-600"></div>
                  </label>
                </div>
                <div>
                  <p className="font-medium text-gray-900 dark:text-white">Open SUMO Visualization</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Opens SUMO-GUI in a separate window to see real-time traffic simulation with moving vehicles and signal changes
                  </p>
                </div>
              </div>

              {/* ML Adaptive Control Toggle */}
              <div className="flex items-start gap-4">
                <div className="flex items-center h-6">
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.useAdaptiveControl}
                      onChange={(e) => updateField('useAdaptiveControl', e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-green-300 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-green-600"></div>
                  </label>
                </div>
                <div>
                  <p className="font-medium text-gray-900 dark:text-white">ML Adaptive Signal Control</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Enable ML-based traffic light control that dynamically adjusts signal timing based on real-time traffic predictions
                  </p>
                </div>
              </div>
            </div>

            {formData.useGui && (
              <div className="p-3 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded-lg">
                <p className="text-sm text-blue-700 dark:text-blue-300">
                  <strong>Note:</strong> SUMO-GUI will open in a separate desktop window. You'll see the actual traffic simulation with vehicles moving on roads and traffic lights changing colors.
                </p>
              </div>
            )}
          </div>

          {/* Error display */}
          {error && (
            <div className="p-4 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg">
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            </div>
          )}

          {/* Submit button */}
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={loading}
              className="btn-primary px-6 py-3 flex items-center space-x-2"
            >
              {loading ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                  <span>Starting...</span>
                </>
              ) : (
                <>
                  <span>Run Simulation</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
