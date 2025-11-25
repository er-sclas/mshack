/**
 * Firestore Hooks for Traffic Data
 *
 * These hooks provide real-time subscriptions to Firestore collections
 * for runs, scenarios, and timeseries data.
 */

import { useState, useEffect } from 'react';
import {
  collection,
  doc,
  query,
  orderBy,
  limit,
  onSnapshot,
  getDocs,
  QueryConstraint,
} from 'firebase/firestore';
import { db } from '../firebase';
import type { Run, Scenario, TimeseriesPoint } from '../types';

// ============================================================================
// useRuns - Subscribe to simulation runs
// ============================================================================

export function useRuns(options?: { status?: string; scenarioId?: string; maxResults?: number }) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    // To avoid requiring Firestore composite indexes, we:
    // 1. Fetch all runs ordered by createdAt
    // 2. Filter by status/scenarioId in memory
    const constraints: QueryConstraint[] = [
      orderBy('createdAt', 'desc'),
      limit(options?.maxResults ? options.maxResults * 3 : 100), // Fetch extra to allow for filtering
    ];

    const q = query(collection(db, 'runs'), ...constraints);

    const unsubscribe = onSnapshot(
      q,
      (snapshot) => {
        let runsData = snapshot.docs.map((doc) => ({
          id: doc.id,
          ...doc.data(),
        })) as Run[];

        // Filter by status in memory (avoids composite index requirement)
        if (options?.status) {
          runsData = runsData.filter((r) => r.status === options.status);
        }

        // Filter by scenarioId in memory
        if (options?.scenarioId) {
          runsData = runsData.filter((r) => r.scenarioId === options.scenarioId);
        }

        // Apply limit after filtering
        if (options?.maxResults) {
          runsData = runsData.slice(0, options.maxResults);
        }

        setRuns(runsData);
        setLoading(false);
      },
      (err) => {
        console.error('Error fetching runs:', err);
        setError(err);
        setLoading(false);
      }
    );

    return () => unsubscribe();
  }, [options?.status, options?.scenarioId, options?.maxResults]);

  return { runs, loading, error };
}

// ============================================================================
// useRun - Subscribe to a single run
// ============================================================================

export function useRun(runId: string | null) {
  const [run, setRun] = useState<Run | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!runId) {
      setRun(null);
      setLoading(false);
      return;
    }

    const docRef = doc(db, 'runs', runId);

    const unsubscribe = onSnapshot(
      docRef,
      (snapshot) => {
        if (snapshot.exists()) {
          setRun({ id: snapshot.id, ...snapshot.data() } as Run);
        } else {
          setRun(null);
        }
        setLoading(false);
      },
      (err) => {
        console.error('Error fetching run:', err);
        setError(err);
        setLoading(false);
      }
    );

    return () => unsubscribe();
  }, [runId]);

  return { run, loading, error };
}

// ============================================================================
// useRunTimeseries - Subscribe to timeseries data for a run
// ============================================================================

export function useRunTimeseries(runId: string | null, maxPoints?: number) {
  const [timeseries, setTimeseries] = useState<TimeseriesPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!runId) {
      setTimeseries([]);
      setLoading(false);
      return;
    }

    const q = query(
      collection(db, 'runs', runId, 'timeseries'),
      orderBy('t', 'asc'),
      limit(maxPoints || 500)
    );

    const unsubscribe = onSnapshot(
      q,
      (snapshot) => {
        const data = snapshot.docs.map((doc) => ({
          id: doc.id,
          ...doc.data(),
        })) as TimeseriesPoint[];
        setTimeseries(data);
        setLoading(false);
      },
      (err) => {
        console.error('Error fetching timeseries:', err);
        setError(err);
        setLoading(false);
      }
    );

    return () => unsubscribe();
  }, [runId, maxPoints]);

  return { timeseries, loading, error };
}

// ============================================================================
// useScenarios - Subscribe to scenarios
// ============================================================================

export function useScenarios(maxResults?: number) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const q = query(
      collection(db, 'scenarios'),
      orderBy('createdAt', 'desc'),
      limit(maxResults || 50)
    );

    const unsubscribe = onSnapshot(
      q,
      (snapshot) => {
        const data = snapshot.docs.map((doc) => ({
          id: doc.id,
          ...doc.data(),
        })) as Scenario[];
        setScenarios(data);
        setLoading(false);
      },
      (err) => {
        console.error('Error fetching scenarios:', err);
        setError(err);
        setLoading(false);
      }
    );

    return () => unsubscribe();
  }, [maxResults]);

  return { scenarios, loading, error };
}

// ============================================================================
// useLatestTimeseries - Get most recent timeseries points
// ============================================================================

export function useLatestTimeseries(runId: string | null, count: number = 12) {
  const [data, setData] = useState<TimeseriesPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!runId) {
      setData([]);
      setLoading(false);
      return;
    }

    const fetchLatest = async () => {
      try {
        const q = query(
          collection(db, 'runs', runId, 'timeseries'),
          orderBy('t', 'desc'),
          limit(count)
        );

        const snapshot = await getDocs(q);
        const points = snapshot.docs
          .map((doc) => ({ id: doc.id, ...doc.data() } as TimeseriesPoint))
          .reverse();

        setData(points);
      } catch (err) {
        console.error('Error fetching latest timeseries:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchLatest();
  }, [runId, count]);

  return { data, loading };
}

// ============================================================================
// useEdgeHistory - Get history for a specific edge
// ============================================================================

export function useEdgeHistory(runId: string | null, edgeId: string | null) {
  const { timeseries, loading, error } = useRunTimeseries(runId);
  const [edgeHistory, setEdgeHistory] = useState<
    Array<{ t: number; speed: number; queueLen: number; hasEvent: boolean }>
  >([]);

  useEffect(() => {
    if (!edgeId || timeseries.length === 0) {
      setEdgeHistory([]);
      return;
    }

    const history = timeseries
      .map((point) => {
        const edgeData = point.metricsByEdge.find((e) => e.edgeId === edgeId);
        if (!edgeData) return null;
        return {
          t: point.t,
          speed: edgeData.avgSpeed,
          queueLen: edgeData.queueLen,
          hasEvent: edgeData.accidentFlag || edgeData.workzoneFlag,
        };
      })
      .filter(Boolean) as Array<{
      t: number;
      speed: number;
      queueLen: number;
      hasEvent: boolean;
    }>;

    setEdgeHistory(history);
  }, [timeseries, edgeId]);

  return { edgeHistory, loading, error };
}

// ============================================================================
// useRegionMetrics - Aggregate metrics by region
// ============================================================================

export function useRegionMetrics(timeseries: TimeseriesPoint[], region: string) {
  const [metrics, setMetrics] = useState<{
    times: number[];
    avgSpeeds: number[];
    totalQueues: number[];
  }>({ times: [], avgSpeeds: [], totalQueues: [] });

  useEffect(() => {
    if (timeseries.length === 0) {
      setMetrics({ times: [], avgSpeeds: [], totalQueues: [] });
      return;
    }

    const times: number[] = [];
    const avgSpeeds: number[] = [];
    const totalQueues: number[] = [];

    for (const point of timeseries) {
      const regionEdges =
        region === 'all'
          ? point.metricsByEdge
          : point.metricsByEdge.filter((e) => e.regionTag === region);

      if (regionEdges.length === 0) continue;

      times.push(point.t);
      avgSpeeds.push(
        regionEdges.reduce((sum, e) => sum + e.avgSpeed, 0) / regionEdges.length
      );
      totalQueues.push(regionEdges.reduce((sum, e) => sum + e.queueLen, 0));
    }

    setMetrics({ times, avgSpeeds, totalQueues });
  }, [timeseries, region]);

  return metrics;
}
