"""
FastAPI Backend for Chepauk Traffic Simulation

This service provides REST APIs for:
- Running traffic simulations
- Retrieving simulation results
- ML-based traffic predictions

Run with: uvicorn main:app --reload --port 8000
"""

import asyncio
import json
import os
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from firestore_client import FirestoreClient, get_firestore_client
from ml_model.model import TrafficPredictor
from chat_service import ChatService, get_chat_service

# ============================================================================
# APP CONFIGURATION
# ============================================================================

app = FastAPI(
    title="Chepauk Traffic Simulation API",
    description="Backend service for traffic simulation and predictive analytics",
    version="1.0.0"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
firestore_client: Optional[FirestoreClient] = None
traffic_predictor: Optional[TrafficPredictor] = None
chat_service: Optional[ChatService] = None

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class AccidentConfig(BaseModel):
    enabled: bool = False
    edgeId: str = ""
    startTime: int = 0
    duration: int = 0
    severity: str = "minor"
    blockedLanes: List[int] = []
    speedReduction: float = 0.5


class RoadWorksConfig(BaseModel):
    enabled: bool = False
    edgeId: str = ""
    startTime: int = 0
    duration: int = 0
    blockedLanes: List[int] = []
    speedReduction: float = 0.3


class ScenarioConfig(BaseModel):
    name: str
    description: str = ""
    demandProfile: str = "normal_day"
    simulationDuration: int = 3600
    accident: AccidentConfig = AccidentConfig()
    roadWorks: RoadWorksConfig = RoadWorksConfig()
    useGui: bool = False  # Launch SUMO-GUI for visualization
    useAdaptiveControl: bool = True  # Enable ML-based signal control


class RunSimulationRequest(BaseModel):
    scenario: ScenarioConfig


class RunSimulationResponse(BaseModel):
    runId: str
    scenarioId: str
    status: str
    message: str


class EdgeHistory(BaseModel):
    edgeId: str
    speeds: List[float]
    queueLens: List[float]
    eventFlags: List[bool] = []


class PredictionRequest(BaseModel):
    runId: Optional[str] = None
    horizonSeconds: int = 300
    stepSeconds: int = 60
    edgeHistories: List[EdgeHistory]


class PredictionResponse(BaseModel):
    predictions: List[Dict[str, Any]]
    model: str
    timestamp: str


class RunSummary(BaseModel):
    id: str
    scenarioId: str
    status: str
    startedAt: Optional[str]
    completedAt: Optional[str]
    summary: Optional[Dict[str, Any]]


class EdgeInfo(BaseModel):
    edgeId: str
    label: str
    region: str


# ============================================================================
# STARTUP / SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global firestore_client, traffic_predictor, chat_service

    try:
        firestore_client = get_firestore_client()
        print("Firestore client initialized")
    except Exception as e:
        print(f"Warning: Could not initialize Firestore: {e}")
        firestore_client = None

    try:
        traffic_predictor = TrafficPredictor()
        print("Traffic predictor initialized")
    except Exception as e:
        print(f"Warning: Could not initialize predictor: {e}")
        traffic_predictor = None

    try:
        chat_service = get_chat_service()
        print("Chat service initialized")
    except Exception as e:
        print(f"Warning: Could not initialize chat service: {e}")
        chat_service = None


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    pass


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "firestore": firestore_client is not None,
        "predictor": traffic_predictor is not None,
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# SIMULATION ENDPOINTS
# ============================================================================

def run_simulation_subprocess(config_path: str, run_id: str, use_gui: bool = False, use_adaptive: bool = True):
    """Run simulation as a subprocess."""
    simulation_dir = Path(__file__).parent.parent / "simulation"
    script_path = simulation_dir / "run_simulation.py"

    cmd = [
        sys.executable,
        str(script_path),
        "--config", config_path
    ]

    # Add GUI flag if requested - this will open SUMO-GUI window
    if use_gui:
        cmd.append("--gui")

    # Add adaptive control flag
    if not use_adaptive:
        cmd.append("--no-adaptive")

    try:
        # Update status to running
        if firestore_client:
            firestore_client.update_run_status(run_id, "running")

        # Set up environment - inherit current env and ensure display access for GUI
        env = os.environ.copy()

        # On macOS, SUMO-GUI uses X11 via XQuartz
        if use_gui:
            import platform
            if platform.system() == 'Darwin':
                # Start XQuartz if not running and set DISPLAY
                try:
                    subprocess.run(['open', '-a', 'XQuartz'], check=False, timeout=5)
                    import time
                    time.sleep(2)  # Give XQuartz time to start
                except Exception as e:
                    print(f"Warning: Could not start XQuartz: {e}")
                # Set DISPLAY for X11
                env['DISPLAY'] = ':0'

        result = subprocess.run(
            cmd,
            cwd=str(simulation_dir),
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout
            env=env
        )

        if result.returncode != 0:
            print(f"Simulation error: {result.stderr}")
            if firestore_client:
                firestore_client.update_run_status(run_id, "failed")

    except subprocess.TimeoutExpired:
        print(f"Simulation timed out for run {run_id}")
        if firestore_client:
            firestore_client.update_run_status(run_id, "failed")

    except Exception as e:
        print(f"Error running simulation: {e}")
        if firestore_client:
            firestore_client.update_run_status(run_id, "failed")


@app.post("/run-simulation", response_model=RunSimulationResponse)
async def run_simulation(request: RunSimulationRequest, background_tasks: BackgroundTasks):
    """
    Start a new traffic simulation.

    This creates a scenario and run in Firestore, then starts the SUMO
    simulation as a background process.
    """
    # Generate IDs
    scenario_id = str(uuid.uuid4())[:8]
    run_id = str(uuid.uuid4())[:8]

    # Build full config
    config = {
        "name": request.scenario.name,
        "description": request.scenario.description,
        "demandProfile": request.scenario.demandProfile,
        "simulationDuration": request.scenario.simulationDuration,
        "stepLength": 1.0,
        "outputInterval": 60,
        "accident": request.scenario.accident.dict(),
        "roadWorks": request.scenario.roadWorks.dict(),
        "regions": {
            "university": ["uni_entrance_in", "uni_entrance_out", "uni_internal_ns", "uni_internal_sn"],
            "stadium": ["stadium_approach_n", "stadium_exit_s", "stadium_internal", "stadium_east_exit"],
            "busy_junction": ["anna_salai_nb", "anna_salai_nb2", "anna_salai_sb", "anna_salai_sb2",
                            "wallajah_eb", "wallajah_eb2", "wallajah_wb", "wallajah_wb2"]
        }
    }

    # Save config to file
    simulation_dir = Path(__file__).parent.parent / "simulation"
    config_path = simulation_dir / "config" / f"run_{run_id}.json"

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    # Create Firestore documents
    if firestore_client:
        try:
            firestore_client.create_scenario(
                scenario_id=scenario_id,
                name=request.scenario.name,
                description=request.scenario.description,
                parameters=config
            )

            firestore_client.create_run(
                run_id=run_id,
                scenario_id=scenario_id
            )
        except Exception as e:
            print(f"Warning: Firestore error: {e}")

    # Start simulation in background
    background_tasks.add_task(
        run_simulation_subprocess,
        f"config/run_{run_id}.json",
        run_id,
        request.scenario.useGui,
        request.scenario.useAdaptiveControl
    )

    gui_msg = " SUMO-GUI window will open." if request.scenario.useGui else ""
    return RunSimulationResponse(
        runId=run_id,
        scenarioId=scenario_id,
        status="pending",
        message=f"Simulation started.{gui_msg} Check /runs/{{runId}} for status."
    )


@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get run metadata and summary."""
    if not firestore_client:
        raise HTTPException(status_code=503, detail="Firestore not available")

    run = firestore_client.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return run


@app.get("/runs/{run_id}/timeseries")
async def get_run_timeseries(
    run_id: str,
    start: Optional[float] = None,
    end: Optional[float] = None,
    limit: int = 500
):
    """Get time-series data for a run."""
    if not firestore_client:
        raise HTTPException(status_code=503, detail="Firestore not available")

    timeseries = firestore_client.get_timeseries(
        run_id=run_id,
        start_time=start,
        end_time=end,
        limit=limit
    )

    return {"runId": run_id, "count": len(timeseries), "data": timeseries}


@app.get("/runs")
async def list_runs(
    scenario_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
):
    """List simulation runs."""
    if not firestore_client:
        raise HTTPException(status_code=503, detail="Firestore not available")

    runs = firestore_client.list_runs(
        scenario_id=scenario_id,
        status=status,
        limit=limit
    )

    return {"count": len(runs), "runs": runs}


@app.delete("/runs/{run_id}")
async def delete_run(run_id: str):
    """Delete a simulation run and its data."""
    if not firestore_client:
        raise HTTPException(status_code=503, detail="Firestore not available")

    firestore_client.delete_run(run_id, delete_timeseries=True)
    return {"message": f"Run {run_id} deleted"}


# ============================================================================
# SCENARIO ENDPOINTS
# ============================================================================

@app.get("/scenarios")
async def list_scenarios(limit: int = 50):
    """List all scenarios."""
    if not firestore_client:
        raise HTTPException(status_code=503, detail="Firestore not available")

    scenarios = firestore_client.list_scenarios(limit=limit)
    return {"count": len(scenarios), "scenarios": scenarios}


@app.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    """Get a scenario by ID."""
    if not firestore_client:
        raise HTTPException(status_code=503, detail="Firestore not available")

    scenario = firestore_client.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    return scenario


# ============================================================================
# PREDICTION ENDPOINTS
# ============================================================================

@app.post("/predict", response_model=PredictionResponse)
async def predict_traffic(request: PredictionRequest):
    """
    Get traffic predictions for specified edges.

    Uses the ML model to predict future traffic conditions based on
    recent history.
    """
    if not traffic_predictor:
        raise HTTPException(status_code=503, detail="Predictor not available")

    try:
        predictions = traffic_predictor.predict(
            edge_histories=request.edgeHistories,
            horizon_seconds=request.horizonSeconds,
            step_seconds=request.stepSeconds
        )

        return PredictionResponse(
            predictions=predictions,
            model=traffic_predictor.model_name,
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")


@app.get("/predict/edges/{run_id}/{edge_id}")
async def predict_edge_traffic(run_id: str, edge_id: str, horizon: int = 300):
    """
    Get predictions for a specific edge using recent data from Firestore.
    """
    if not firestore_client or not traffic_predictor:
        raise HTTPException(status_code=503, detail="Services not available")

    # Get recent history
    history = firestore_client.get_edge_history(run_id, edge_id, limit=24)

    if len(history) < 6:
        raise HTTPException(
            status_code=400,
            detail="Not enough historical data for prediction"
        )

    # Build edge history
    edge_history = EdgeHistory(
        edgeId=edge_id,
        speeds=[h["avgSpeed"] for h in history],
        queueLens=[h["queueLen"] for h in history],
        eventFlags=[h.get("accidentFlag", False) or h.get("workzoneFlag", False) for h in history]
    )

    predictions = traffic_predictor.predict(
        edge_histories=[edge_history],
        horizon_seconds=horizon,
        step_seconds=60
    )

    return {
        "edgeId": edge_id,
        "runId": run_id,
        "historyLength": len(history),
        "predictions": predictions
    }


# ============================================================================
# EDGE METADATA
# ============================================================================

# Edge labels for human-readable display
EDGE_LABELS = {
    "anna_salai_nb": "Anna Salai (Northbound)",
    "anna_salai_nb2": "Anna Salai North (Northbound)",
    "anna_salai_sb": "Anna Salai (Southbound)",
    "anna_salai_sb2": "Anna Salai South (Southbound)",
    "wallajah_eb": "Wallajah Road (Eastbound)",
    "wallajah_eb2": "Wallajah Road East (Eastbound)",
    "wallajah_wb": "Wallajah Road (Westbound)",
    "wallajah_wb2": "Wallajah Road West (Westbound)",
    "uni_entrance_in": "University Entrance (Inbound)",
    "uni_entrance_out": "University Entrance (Outbound)",
    "uni_internal_ns": "University Internal (N-S)",
    "uni_internal_sn": "University Internal (S-N)",
    "uni_north_conn": "University North Connector",
    "uni_north_conn_rev": "University North Connector (Rev)",
    "stadium_approach_n": "Stadium Approach (North)",
    "stadium_approach_n_rev": "Stadium Approach North (Outbound)",
    "stadium_exit_s": "Stadium Exit (South)",
    "stadium_exit_s_rev": "Stadium Exit South (Inbound)",
    "stadium_internal": "Stadium Internal Road",
    "stadium_internal_rev": "Stadium Internal (Reverse)",
    "stadium_east_exit": "Stadium East Exit",
    "stadium_east_entry": "Stadium East Entry",
    "kamarajar_nb": "Kamarajar Salai (Northbound)",
    "kamarajar_nb2": "Kamarajar Salai North (Northbound)",
    "kamarajar_sb": "Kamarajar Salai (Southbound)",
    "kamarajar_sb2": "Kamarajar Salai South (Southbound)",
}

EDGE_REGIONS = {
    "university": ["uni_entrance_in", "uni_entrance_out", "uni_internal_ns", "uni_internal_sn",
                   "uni_north_conn", "uni_north_conn_rev"],
    "stadium": ["stadium_approach_n", "stadium_approach_n_rev", "stadium_exit_s", "stadium_exit_s_rev",
                "stadium_internal", "stadium_internal_rev", "stadium_east_exit", "stadium_east_entry"],
    "busy_junction": ["anna_salai_nb", "anna_salai_nb2", "anna_salai_sb", "anna_salai_sb2",
                      "wallajah_eb", "wallajah_eb2", "wallajah_wb", "wallajah_wb2"],
    "kamarajar": ["kamarajar_nb", "kamarajar_nb2", "kamarajar_sb", "kamarajar_sb2"]
}


@app.get("/edges")
async def list_edges():
    """Get list of all edges with labels and regions."""
    edges = []

    for region, edge_ids in EDGE_REGIONS.items():
        for edge_id in edge_ids:
            edges.append(EdgeInfo(
                edgeId=edge_id,
                label=EDGE_LABELS.get(edge_id, edge_id),
                region=region
            ))

    return {"count": len(edges), "edges": edges}


@app.get("/edges/by-region/{region}")
async def get_edges_by_region(region: str):
    """Get edges for a specific region."""
    if region not in EDGE_REGIONS:
        raise HTTPException(status_code=404, detail="Region not found")

    edges = [
        EdgeInfo(
            edgeId=edge_id,
            label=EDGE_LABELS.get(edge_id, edge_id),
            region=region
        )
        for edge_id in EDGE_REGIONS[region]
    ]

    return {"region": region, "edges": edges}


# ============================================================================
# SUMO NETWORK ENDPOINTS
# ============================================================================

def parse_sumo_network(net_file: Path) -> Dict[str, Any]:
    """Parse SUMO network XML and extract nodes, edges, and junctions."""
    tree = ET.parse(net_file)
    root = tree.getroot()

    # Get network bounds from location element
    location = root.find('location')
    bounds = {
        "netOffset": location.get('netOffset', '0,0') if location is not None else '0,0',
        "convBoundary": location.get('convBoundary', '0,0,100,100') if location is not None else '0,0,100,100'
    }

    # Parse boundary
    conv_bounds = bounds['convBoundary'].split(',')
    min_x, min_y, max_x, max_y = float(conv_bounds[0]), float(conv_bounds[1]), float(conv_bounds[2]), float(conv_bounds[3])

    # Parse junctions (nodes)
    junctions = []
    for junction in root.findall('junction'):
        junc_id = junction.get('id', '')
        junc_type = junction.get('type', '')

        # Skip internal junctions
        if junc_id.startswith(':'):
            continue

        x = float(junction.get('x', 0))
        y = float(junction.get('y', 0))

        junctions.append({
            "id": junc_id,
            "type": junc_type,
            "x": x,
            "y": y,
            "shape": junction.get('shape', '')
        })

    # Parse edges
    edges = []
    for edge in root.findall('edge'):
        edge_id = edge.get('id', '')

        # Skip internal edges
        if edge_id.startswith(':'):
            continue

        from_node = edge.get('from', '')
        to_node = edge.get('to', '')

        # Get lane shapes
        lanes = []
        for lane in edge.findall('lane'):
            shape = lane.get('shape', '')
            if shape:
                # Parse shape string "x1,y1 x2,y2 ..." into list of points
                points = []
                for point in shape.split():
                    coords = point.split(',')
                    if len(coords) >= 2:
                        points.append({
                            "x": float(coords[0]),
                            "y": float(coords[1])
                        })
                lanes.append({
                    "id": lane.get('id', ''),
                    "speed": float(lane.get('speed', 13.89)),
                    "length": float(lane.get('length', 0)),
                    "shape": points
                })

        # Determine region based on edge ID
        region = "other"
        for reg, edge_ids in EDGE_REGIONS.items():
            if edge_id in edge_ids:
                region = reg
                break

        edges.append({
            "id": edge_id,
            "from": from_node,
            "to": to_node,
            "lanes": lanes,
            "region": region,
            "label": EDGE_LABELS.get(edge_id, edge_id)
        })

    return {
        "bounds": {
            "minX": min_x,
            "minY": min_y,
            "maxX": max_x,
            "maxY": max_y
        },
        "junctions": junctions,
        "edges": edges
    }


@app.get("/network")
async def get_sumo_network():
    """
    Get the SUMO network geometry for visualization.

    Returns parsed network data including junctions, edges, and their shapes.
    """
    simulation_dir = Path(__file__).parent.parent / "simulation"
    net_file = simulation_dir / "chepauk.net.xml"

    if not net_file.exists():
        raise HTTPException(status_code=404, detail="Network file not found")

    try:
        network = parse_sumo_network(net_file)
        return network
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing network: {str(e)}")


# ============================================================================
# COMPARISON ENDPOINTS
# ============================================================================

@app.get("/compare")
async def compare_runs(run_ids: str):
    """
    Compare multiple simulation runs.

    Args:
        run_ids: Comma-separated list of run IDs
    """
    if not firestore_client:
        raise HTTPException(status_code=503, detail="Firestore not available")

    ids = [r.strip() for r in run_ids.split(",")]

    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 run IDs")

    if len(ids) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 runs for comparison")

    comparisons = firestore_client.get_run_summary_comparison(ids)

    return {
        "runs": comparisons,
        "count": len(comparisons)
    }


@app.get("/compare/timeseries")
async def compare_timeseries(run_ids: str, metric: str = "avgSpeed"):
    """
    Get time-series data for multiple runs for comparison charts.

    Args:
        run_ids: Comma-separated list of run IDs
        metric: Metric to compare (avgSpeed, totalDelay, totalQueueLength)
    """
    if not firestore_client:
        raise HTTPException(status_code=503, detail="Firestore not available")

    ids = [r.strip() for r in run_ids.split(",")]
    valid_metrics = ["avgSpeed", "totalDelay", "totalQueueLength", "numVehicles"]

    if metric not in valid_metrics:
        raise HTTPException(status_code=400, detail=f"Invalid metric. Use one of: {valid_metrics}")

    result = {}

    for run_id in ids:
        timeseries = firestore_client.get_timeseries(run_id, limit=500)
        result[run_id] = [
            {"t": ts["t"], "value": ts["metricsGlobal"].get(metric, 0)}
            for ts in timeseries
        ]

    return {"metric": metric, "series": result}


# ============================================================================
# TRAFFIC LIGHT & LIVE STATE ENDPOINTS
# ============================================================================

def parse_traffic_lights(net_file: Path) -> List[Dict[str, Any]]:
    """Parse traffic light definitions from SUMO network XML."""
    tree = ET.parse(net_file)
    root = tree.getroot()

    traffic_lights = []

    # Parse tlLogic elements
    for tl in root.findall('tlLogic'):
        tls_id = tl.get('id', '')
        tl_type = tl.get('type', 'static')

        phases = []
        for phase in tl.findall('phase'):
            phases.append({
                "duration": float(phase.get('duration', 30)),
                "state": phase.get('state', ''),
                "minDur": float(phase.get('minDur', 5)) if phase.get('minDur') else None,
                "maxDur": float(phase.get('maxDur', 50)) if phase.get('maxDur') else None
            })

        traffic_lights.append({
            "id": tls_id,
            "type": tl_type,
            "phaseCount": len(phases),
            "phases": phases
        })

    # Get junction positions for traffic lights
    tl_positions = {}
    for junction in root.findall('junction'):
        junc_id = junction.get('id', '')
        junc_type = junction.get('type', '')

        if junc_type == 'traffic_light':
            tl_positions[junc_id] = {
                "x": float(junction.get('x', 0)),
                "y": float(junction.get('y', 0))
            }

    # Add positions to traffic lights
    for tl in traffic_lights:
        if tl["id"] in tl_positions:
            tl["position"] = tl_positions[tl["id"]]

    return traffic_lights


@app.get("/network/traffic-lights")
async def get_traffic_lights():
    """
    Get traffic light configurations from the SUMO network.

    Returns all traffic light IDs, phases, and positions.
    """
    simulation_dir = Path(__file__).parent.parent / "simulation"
    net_file = simulation_dir / "chepauk.net.xml"

    if not net_file.exists():
        raise HTTPException(status_code=404, detail="Network file not found")

    try:
        traffic_lights = parse_traffic_lights(net_file)
        return {
            "count": len(traffic_lights),
            "trafficLights": traffic_lights
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing traffic lights: {str(e)}")


@app.get("/runs/{run_id}/live-state")
async def get_run_live_state(run_id: str):
    """
    Get the latest traffic state for a running simulation.

    This endpoint provides real-time data for live visualization:
    - Signal states (current phase, time in phase)
    - Vehicle counts and positions
    - Active events
    """
    if not firestore_client:
        raise HTTPException(status_code=503, detail="Firestore not available")

    # Get the most recent timeseries point
    timeseries = firestore_client.get_timeseries(run_id, limit=1)

    if not timeseries:
        raise HTTPException(status_code=404, detail="No data available for this run")

    latest = timeseries[0]

    # Get run status
    run = firestore_client.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return {
        "runId": run_id,
        "status": run.get("status", "unknown"),
        "simTime": latest.get("t", 0),
        "timestamp": latest.get("timestamp"),
        "metricsGlobal": latest.get("metricsGlobal", {}),
        "signalStates": latest.get("signalStates", []),
        "vehicleCount": latest.get("vehicleCount", 0),
        "adaptiveControl": latest.get("adaptiveControl", False),
        "activeEvents": [
            edge["edgeId"] for edge in latest.get("metricsByEdge", [])
            if edge.get("accidentFlag") or edge.get("workzoneFlag")
        ]
    }


@app.get("/runs/{run_id}/signal-history")
async def get_signal_history(run_id: str, tls_id: Optional[str] = None, limit: int = 100):
    """
    Get signal state history for a run.

    Useful for analyzing signal timing patterns and ML control decisions.
    """
    if not firestore_client:
        raise HTTPException(status_code=503, detail="Firestore not available")

    timeseries = firestore_client.get_timeseries(run_id, limit=limit)

    signal_history = []
    for ts in timeseries:
        signal_states = ts.get("signalStates", [])
        if tls_id:
            signal_states = [s for s in signal_states if s.get("tlsId") == tls_id]

        if signal_states:
            signal_history.append({
                "t": ts.get("t"),
                "signals": signal_states
            })

    return {
        "runId": run_id,
        "tlsId": tls_id,
        "count": len(signal_history),
        "history": signal_history
    }


@app.get("/runs/{run_id}/edge-metrics/{edge_id}")
async def get_edge_metrics_history(run_id: str, edge_id: str, limit: int = 200):
    """
    Get metrics history for a specific edge.

    Returns time-series data for visualization and analysis.
    """
    if not firestore_client:
        raise HTTPException(status_code=503, detail="Firestore not available")

    timeseries = firestore_client.get_timeseries(run_id, limit=limit)

    edge_history = []
    for ts in timeseries:
        edge_data = None
        for edge in ts.get("metricsByEdge", []):
            if edge.get("edgeId") == edge_id:
                edge_data = edge
                break

        if edge_data:
            edge_history.append({
                "t": ts.get("t"),
                "avgSpeed": edge_data.get("avgSpeed", 0),
                "queueLen": edge_data.get("queueLen", 0),
                "flow": edge_data.get("flow", 0),
                "waitingTime": edge_data.get("waitingTime", 0),
                "hasEvent": edge_data.get("accidentFlag", False) or edge_data.get("workzoneFlag", False)
            })

    return {
        "runId": run_id,
        "edgeId": edge_id,
        "label": EDGE_LABELS.get(edge_id, edge_id),
        "count": len(edge_history),
        "history": edge_history
    }


# ============================================================================
# CHAT ENDPOINTS
# ============================================================================

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    runId: Optional[str] = None
    conversationHistory: List[ChatMessage] = []
    includeVoice: bool = False


class ChatResponse(BaseModel):
    response: str
    audioUrl: Optional[str] = None
    timestamp: str


@app.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(request: ChatRequest):
    """
    Chat with the AI assistant about traffic simulations.

    The assistant can analyze simulation data and explain results.
    Optionally includes text-to-speech audio response.
    """
    if not chat_service:
        raise HTTPException(status_code=503, detail="Chat service not available")

    # Get run data if runId provided
    run_data = None
    if request.runId and firestore_client:
        try:
            run = firestore_client.get_run(request.runId)
            timeseries = firestore_client.get_timeseries(request.runId, limit=50)
            run_data = {
                "run": run,
                "timeseries_sample": timeseries[:20] if timeseries else [],
                "total_data_points": len(timeseries),
            }
        except Exception as e:
            print(f"Error fetching run data: {e}")

    # Convert conversation history
    history = [{"role": m.role, "content": m.content} for m in request.conversationHistory]

    # Get LLM response
    response_text = await chat_service.chat(
        message=request.message,
        run_data=run_data,
        conversation_history=history,
    )

    result = ChatResponse(
        response=response_text,
        audioUrl=None,
        timestamp=datetime.utcnow().isoformat(),
    )

    return result


@app.post("/chat/transcribe")
async def transcribe_audio(audio: bytes = None):
    """
    Transcribe audio to text using Whisper.

    Accepts audio file upload and returns transcribed text.
    """
    from fastapi import File, UploadFile

    raise HTTPException(status_code=501, detail="Use /chat/transcribe-upload instead")


from fastapi import File, UploadFile
from fastapi.responses import Response


@app.post("/chat/transcribe-upload")
async def transcribe_audio_upload(file: UploadFile = File(...)):
    """
    Transcribe uploaded audio file to text using Whisper on Groq.
    """
    if not chat_service:
        raise HTTPException(status_code=503, detail="Chat service not available")

    audio_data = await file.read()
    text = await chat_service.transcribe_audio(audio_data, file.filename or "audio.webm")

    return {"text": text, "filename": file.filename}


@app.post("/chat/tts")
async def text_to_speech(text: str):
    """
    Convert text to speech using ElevenLabs.

    Returns audio data as MP3.
    """
    if not chat_service:
        raise HTTPException(status_code=503, detail="Chat service not available")

    audio_data = await chat_service.text_to_speech(text)

    if not audio_data:
        raise HTTPException(status_code=500, detail="Failed to generate speech")

    return Response(
        content=audio_data,
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline; filename=speech.mp3"},
    )


class TTSRequest(BaseModel):
    text: str
    voiceId: Optional[str] = None


@app.post("/chat/tts-json")
async def text_to_speech_json(request: TTSRequest):
    """
    Convert text to speech using ElevenLabs.

    Returns audio data as base64 encoded string.
    """
    import base64

    if not chat_service:
        raise HTTPException(status_code=503, detail="Chat service not available")

    audio_data = await chat_service.text_to_speech(request.text, request.voiceId)

    if not audio_data:
        raise HTTPException(status_code=500, detail="Failed to generate speech")

    audio_base64 = base64.b64encode(audio_data).decode("utf-8")

    return {
        "audio": audio_base64,
        "format": "mp3",
        "textLength": len(request.text),
    }


@app.post("/chat/analyze/{run_id}")
async def analyze_simulation_run(run_id: str):
    """
    Generate a comprehensive AI analysis of a simulation run.

    This provides detailed insights about performance, ML decisions,
    and comparisons with static control.
    """
    if not chat_service or not firestore_client:
        raise HTTPException(status_code=503, detail="Services not available")

    # Get run data
    run = firestore_client.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    timeseries = firestore_client.get_timeseries(run_id, limit=100)

    # Generate analysis
    analysis = await chat_service.analyze_simulation(
        run_summary=run.get("summary", {}),
        timeseries_data=timeseries,
    )

    return {
        "runId": run_id,
        "analysis": analysis,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
