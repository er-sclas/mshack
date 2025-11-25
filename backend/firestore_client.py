"""
Firestore Client for Traffic Simulation Data

This module provides a clean interface for storing and retrieving traffic
simulation data from Google Cloud Firestore.

Data Structure:
- /scenarios/{scenarioId}: Scenario definitions and parameters
- /runs/{runId}: Simulation run metadata and summaries
- /runs/{runId}/timeseries/{stepId}: Time-series traffic data

Setup:
1. Create a Firebase project at https://console.firebase.google.com
2. Enable Firestore Database (Native mode)
3. Generate a service account key (Project Settings -> Service Accounts)
4. Set GOOGLE_APPLICATION_CREDENTIALS environment variable to the key path
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from google.cloud import firestore
from google.oauth2 import service_account


class FirestoreClient:
    """Client for Firestore operations on traffic simulation data."""

    def __init__(self, credentials_path: Optional[str] = None, project_id: Optional[str] = None):
        """
        Initialize Firestore client.

        Args:
            credentials_path: Path to service account JSON. If None, uses
                              GOOGLE_APPLICATION_CREDENTIALS env var.
            project_id: Firebase project ID. If None, uses FIRESTORE_PROJECT_ID
                        env var or infers from credentials.
        """
        self.credentials_path = credentials_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        self.project_id = project_id or os.environ.get("FIRESTORE_PROJECT_ID")

        if self.credentials_path and os.path.exists(self.credentials_path):
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path
            )
            self.db = firestore.Client(credentials=credentials, project=self.project_id)
        else:
            # Try default credentials (for local emulator or GCP environment)
            self.db = firestore.Client(project=self.project_id)

    # =========================================================================
    # SCENARIOS
    # =========================================================================

    def create_scenario(
        self,
        scenario_id: str,
        name: str,
        description: str,
        parameters: Dict[str, Any]
    ) -> str:
        """
        Create a new scenario document.

        Args:
            scenario_id: Unique scenario identifier
            name: Human-readable scenario name
            description: Scenario description
            parameters: Full scenario configuration

        Returns:
            The scenario ID
        """
        doc_ref = self.db.collection("scenarios").document(scenario_id)
        doc_ref.set({
            "name": name,
            "description": description,
            "parameters": parameters,
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat()
        })
        return scenario_id

    def get_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """Get a scenario by ID."""
        doc = self.db.collection("scenarios").document(scenario_id).get()
        if doc.exists:
            return {"id": doc.id, **doc.to_dict()}
        return None

    def list_scenarios(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List all scenarios, most recent first."""
        docs = (
            self.db.collection("scenarios")
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]

    def delete_scenario(self, scenario_id: str) -> bool:
        """Delete a scenario."""
        self.db.collection("scenarios").document(scenario_id).delete()
        return True

    # =========================================================================
    # RUNS
    # =========================================================================

    def create_run(
        self,
        run_id: str,
        scenario_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new simulation run document.

        Args:
            run_id: Unique run identifier
            scenario_id: Associated scenario ID
            metadata: Additional run metadata

        Returns:
            The run ID
        """
        doc_ref = self.db.collection("runs").document(run_id)
        doc_ref.set({
            "scenarioId": scenario_id,
            "status": "pending",
            "startedAt": datetime.utcnow().isoformat(),
            "completedAt": None,
            "summary": None,
            "metadata": metadata or {},
            "createdAt": datetime.utcnow().isoformat()
        })
        return run_id

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get a run by ID."""
        doc = self.db.collection("runs").document(run_id).get()
        if doc.exists:
            return {"id": doc.id, **doc.to_dict()}
        return None

    def list_runs(
        self,
        scenario_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List runs with optional filters.

        Args:
            scenario_id: Filter by scenario
            status: Filter by status (pending/running/completed)
            limit: Maximum number of results

        Returns:
            List of run documents
        """
        query = self.db.collection("runs")

        # Note: To avoid requiring composite indexes, we filter in memory
        # when both status and ordering are needed
        if scenario_id:
            query = query.where(filter=firestore.FieldFilter("scenarioId", "==", scenario_id))

        # If status filter is needed, fetch all and filter in memory
        # This avoids the composite index requirement
        if status:
            # Get all runs ordered by createdAt, then filter
            query = query.order_by("createdAt", direction=firestore.Query.DESCENDING)
            all_runs = [{"id": doc.id, **doc.to_dict()} for doc in query.stream()]
            filtered = [r for r in all_runs if r.get("status") == status]
            return filtered[:limit]
        else:
            query = query.order_by("createdAt", direction=firestore.Query.DESCENDING)
            query = query.limit(limit)
            return [{"id": doc.id, **doc.to_dict()} for doc in query.stream()]

    def update_run_status(
        self,
        run_id: str,
        status: str,
        summary: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update run status and optionally set summary.

        Args:
            run_id: Run identifier
            status: New status (pending/running/completed/failed)
            summary: Run summary statistics

        Returns:
            True if update succeeded
        """
        doc_ref = self.db.collection("runs").document(run_id)
        update_data = {
            "status": status,
            "updatedAt": datetime.utcnow().isoformat()
        }

        if status == "running":
            update_data["startedAt"] = datetime.utcnow().isoformat()

        if status in ["completed", "failed"]:
            update_data["completedAt"] = datetime.utcnow().isoformat()

        if summary:
            update_data["summary"] = summary

        doc_ref.update(update_data)
        return True

    def delete_run(self, run_id: str, delete_timeseries: bool = True) -> bool:
        """
        Delete a run and optionally its timeseries data.

        Args:
            run_id: Run identifier
            delete_timeseries: If True, also delete all timeseries documents

        Returns:
            True if deletion succeeded
        """
        if delete_timeseries:
            # Delete all timeseries documents in batches
            timeseries_ref = self.db.collection("runs").document(run_id).collection("timeseries")
            self._delete_collection(timeseries_ref)

        self.db.collection("runs").document(run_id).delete()
        return True

    def _delete_collection(self, collection_ref, batch_size: int = 100):
        """Helper to delete all documents in a collection."""
        docs = collection_ref.limit(batch_size).stream()
        deleted = 0

        for doc in docs:
            doc.reference.delete()
            deleted += 1

        if deleted >= batch_size:
            return self._delete_collection(collection_ref, batch_size)

    # =========================================================================
    # TIMESERIES DATA
    # =========================================================================

    def add_timeseries_data(
        self,
        run_id: str,
        step_id: str,
        data: Dict[str, Any]
    ) -> str:
        """
        Add a timestep's data to a run.

        Args:
            run_id: Run identifier
            step_id: Unique step identifier (e.g., "step_000060")
            data: Timestep data including metricsGlobal and metricsByEdge

        Returns:
            The step ID
        """
        doc_ref = (
            self.db.collection("runs")
            .document(run_id)
            .collection("timeseries")
            .document(step_id)
        )
        doc_ref.set({
            **data,
            "createdAt": datetime.utcnow().isoformat()
        })
        return step_id

    def get_timeseries(
        self,
        run_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get timeseries data for a run.

        Args:
            run_id: Run identifier
            start_time: Filter by simulation time >= start_time
            end_time: Filter by simulation time <= end_time
            limit: Maximum number of documents

        Returns:
            List of timestep documents ordered by time
        """
        query = (
            self.db.collection("runs")
            .document(run_id)
            .collection("timeseries")
        )

        if start_time is not None:
            query = query.where("t", ">=", start_time)

        if end_time is not None:
            query = query.where("t", "<=", end_time)

        query = query.order_by("t").limit(limit)

        return [{"id": doc.id, **doc.to_dict()} for doc in query.stream()]

    def get_latest_timeseries(self, run_id: str, count: int = 12) -> List[Dict[str, Any]]:
        """
        Get the most recent timeseries data points.

        Args:
            run_id: Run identifier
            count: Number of recent points to retrieve

        Returns:
            List of most recent timestep documents
        """
        query = (
            self.db.collection("runs")
            .document(run_id)
            .collection("timeseries")
            .order_by("t", direction=firestore.Query.DESCENDING)
            .limit(count)
        )

        results = [{"id": doc.id, **doc.to_dict()} for doc in query.stream()]
        return list(reversed(results))  # Return in chronological order

    def get_edge_history(
        self,
        run_id: str,
        edge_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get historical data for a specific edge.

        Args:
            run_id: Run identifier
            edge_id: Edge identifier
            limit: Maximum number of points

        Returns:
            List of edge metrics over time
        """
        timeseries = self.get_timeseries(run_id, limit=limit)

        edge_history = []
        for step in timeseries:
            edge_data = next(
                (e for e in step.get("metricsByEdge", []) if e["edgeId"] == edge_id),
                None
            )
            if edge_data:
                edge_history.append({
                    "t": step["t"],
                    **edge_data
                })

        return edge_history

    # =========================================================================
    # AGGREGATIONS
    # =========================================================================

    def get_run_summary_comparison(self, run_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get summary data for multiple runs for comparison.

        Args:
            run_ids: List of run identifiers

        Returns:
            List of run summaries
        """
        summaries = []
        for run_id in run_ids:
            run = self.get_run(run_id)
            if run:
                summaries.append({
                    "runId": run_id,
                    "scenarioId": run.get("scenarioId"),
                    "status": run.get("status"),
                    "summary": run.get("summary")
                })
        return summaries

    def get_region_aggregates(
        self,
        run_id: str,
        region: str
    ) -> Dict[str, Any]:
        """
        Get aggregated metrics for a specific region.

        Args:
            run_id: Run identifier
            region: Region tag (university/stadium/busy_junction)

        Returns:
            Aggregated metrics for the region
        """
        timeseries = self.get_timeseries(run_id)

        region_metrics = {
            "region": region,
            "avgSpeed": [],
            "totalFlow": [],
            "totalQueueLen": []
        }

        for step in timeseries:
            edges = [
                e for e in step.get("metricsByEdge", [])
                if e.get("regionTag") == region
            ]

            if edges:
                region_metrics["avgSpeed"].append(
                    sum(e["avgSpeed"] for e in edges) / len(edges)
                )
                region_metrics["totalFlow"].append(
                    sum(e["flow"] for e in edges)
                )
                region_metrics["totalQueueLen"].append(
                    sum(e["queueLen"] for e in edges)
                )

        # Calculate overall averages
        if region_metrics["avgSpeed"]:
            region_metrics["overallAvgSpeed"] = sum(region_metrics["avgSpeed"]) / len(region_metrics["avgSpeed"])
            region_metrics["overallAvgFlow"] = sum(region_metrics["totalFlow"]) / len(region_metrics["totalFlow"])
            region_metrics["overallAvgQueueLen"] = sum(region_metrics["totalQueueLen"]) / len(region_metrics["totalQueueLen"])

        return region_metrics


# Convenience function for quick access
def get_firestore_client() -> FirestoreClient:
    """Get a FirestoreClient instance using environment configuration."""
    return FirestoreClient()
