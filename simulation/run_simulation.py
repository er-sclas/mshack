#!/usr/bin/env python3
"""
SUMO Traffic Simulation Runner with TraCI

This script runs SUMO simulations with dynamic event injection (accidents, road works)
and streams results to Firestore for real-time monitoring and analysis.

Usage:
    python run_simulation.py [--config CONFIG_FILE] [--gui] [--no-firestore]

Examples:
    python run_simulation.py
    python run_simulation.py --config config/match_day_accident.json
    python run_simulation.py --gui --config config/roadworks_scenario.json
"""

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add SUMO tools to path
if "SUMO_HOME" in os.environ:
    sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
else:
    # Try common locations
    for path in ["/usr/share/sumo/tools", "/opt/homebrew/share/sumo/tools"]:
        if os.path.exists(path):
            sys.path.append(path)
            break

try:
    import traci
    import traci.constants as tc
except ImportError:
    print("ERROR: Cannot import TraCI. Please ensure SUMO is installed and SUMO_HOME is set.")
    sys.exit(1)

# Import Firestore client (optional)
try:
    sys.path.append(str(Path(__file__).parent.parent / "backend"))
    from firestore_client import FirestoreClient
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False
    print("WARNING: Firestore client not available. Running in local-only mode.")

# Import adaptive controller
try:
    from adaptive_controller import AdaptiveSignalController
    ADAPTIVE_CONTROLLER_AVAILABLE = True
except ImportError:
    ADAPTIVE_CONTROLLER_AVAILABLE = False
    print("WARNING: Adaptive controller not available. Using fixed signal timing.")


class DynamicEvent:
    """Base class for dynamic traffic events."""

    def __init__(self, edge_id: str, start_time: float, duration: float):
        self.edge_id = edge_id
        self.start_time = start_time
        self.duration = duration
        self.end_time = start_time + duration
        self.is_active = False
        self.original_state: Dict[str, Any] = {}

    def should_activate(self, sim_time: float) -> bool:
        return not self.is_active and sim_time >= self.start_time

    def should_deactivate(self, sim_time: float) -> bool:
        return self.is_active and sim_time >= self.end_time

    def activate(self):
        """Activate the event - override in subclasses."""
        raise NotImplementedError

    def deactivate(self):
        """Deactivate the event - override in subclasses."""
        raise NotImplementedError


class AccidentEvent(DynamicEvent):
    """Simulates an accident on a road edge."""

    def __init__(
        self,
        edge_id: str,
        start_time: float,
        duration: float,
        severity: str = "minor",
        blocked_lanes: Optional[List[int]] = None,
        speed_reduction: float = 0.5
    ):
        super().__init__(edge_id, start_time, duration)
        self.severity = severity
        self.blocked_lanes = blocked_lanes or []
        self.speed_reduction = speed_reduction

    def activate(self):
        """Block lanes and reduce speed to simulate accident."""
        if self.is_active:
            return

        print(f"[{traci.simulation.getTime():.0f}s] ACCIDENT ACTIVATED on {self.edge_id}")

        try:
            # Store original state
            self.original_state["max_speed"] = traci.edge.getMaxSpeed(self.edge_id)

            # Get lane count
            lane_count = traci.edge.getLaneNumber(self.edge_id)

            # Block specified lanes
            for lane_idx in self.blocked_lanes:
                if lane_idx < lane_count:
                    lane_id = f"{self.edge_id}_{lane_idx}"
                    # Disallow all vehicle classes on this lane
                    traci.lane.setDisallowed(lane_id, ["all"])
                    print(f"  Blocked lane: {lane_id}")

            # Reduce speed on remaining lanes
            new_speed = self.original_state["max_speed"] * self.speed_reduction
            for lane_idx in range(lane_count):
                if lane_idx not in self.blocked_lanes:
                    lane_id = f"{self.edge_id}_{lane_idx}"
                    traci.lane.setMaxSpeed(lane_id, new_speed)

            self.is_active = True

        except traci.TraCIException as e:
            print(f"  Warning: Could not fully activate accident: {e}")

    def deactivate(self):
        """Restore normal conditions."""
        if not self.is_active:
            return

        print(f"[{traci.simulation.getTime():.0f}s] ACCIDENT CLEARED on {self.edge_id}")

        try:
            lane_count = traci.edge.getLaneNumber(self.edge_id)

            # Restore all lanes
            for lane_idx in range(lane_count):
                lane_id = f"{self.edge_id}_{lane_idx}"
                # Re-allow all vehicles
                traci.lane.setAllowed(lane_id, [])
                # Restore original speed
                traci.lane.setMaxSpeed(lane_id, self.original_state.get("max_speed", 13.89))

            self.is_active = False

        except traci.TraCIException as e:
            print(f"  Warning: Could not fully deactivate accident: {e}")


class RoadWorksEvent(DynamicEvent):
    """Simulates road works / construction zone."""

    def __init__(
        self,
        edge_id: str,
        start_time: float,
        duration: float,
        blocked_lanes: Optional[List[int]] = None,
        speed_reduction: float = 0.3
    ):
        super().__init__(edge_id, start_time, duration)
        self.blocked_lanes = blocked_lanes or []
        self.speed_reduction = speed_reduction

    def activate(self):
        """Set up road works zone."""
        if self.is_active:
            return

        print(f"[{traci.simulation.getTime():.0f}s] ROAD WORKS STARTED on {self.edge_id}")

        try:
            self.original_state["max_speed"] = traci.edge.getMaxSpeed(self.edge_id)
            lane_count = traci.edge.getLaneNumber(self.edge_id)

            # Block specified lanes
            for lane_idx in self.blocked_lanes:
                if lane_idx < lane_count:
                    lane_id = f"{self.edge_id}_{lane_idx}"
                    traci.lane.setDisallowed(lane_id, ["all"])
                    print(f"  Blocked lane: {lane_id}")

            # Reduce speed significantly on all lanes
            new_speed = self.original_state["max_speed"] * self.speed_reduction
            for lane_idx in range(lane_count):
                lane_id = f"{self.edge_id}_{lane_idx}"
                traci.lane.setMaxSpeed(lane_id, new_speed)

            self.is_active = True

        except traci.TraCIException as e:
            print(f"  Warning: Could not fully activate road works: {e}")

    def deactivate(self):
        """Remove road works zone."""
        if not self.is_active:
            return

        print(f"[{traci.simulation.getTime():.0f}s] ROAD WORKS COMPLETED on {self.edge_id}")

        try:
            lane_count = traci.edge.getLaneNumber(self.edge_id)

            for lane_idx in range(lane_count):
                lane_id = f"{self.edge_id}_{lane_idx}"
                traci.lane.setAllowed(lane_id, [])
                traci.lane.setMaxSpeed(lane_id, self.original_state.get("max_speed", 13.89))

            self.is_active = False

        except traci.TraCIException as e:
            print(f"  Warning: Could not fully deactivate road works: {e}")


class TrafficMetricsCollector:
    """Collects traffic metrics from SUMO simulation."""

    def __init__(self, regions: Dict[str, List[str]]):
        self.regions = regions
        self.all_edges: List[str] = []

    def initialize(self):
        """Initialize after SUMO connection."""
        self.all_edges = list(traci.edge.getIDList())
        # Filter out internal edges (start with ':')
        self.all_edges = [e for e in self.all_edges if not e.startswith(':')]

    def get_edge_region(self, edge_id: str) -> str:
        """Determine which region an edge belongs to."""
        for region, edges in self.regions.items():
            if edge_id in edges:
                return region
        return "other"

    def collect_global_metrics(self) -> Dict[str, float]:
        """Collect global simulation metrics."""
        try:
            # Get all vehicles
            vehicle_ids = traci.vehicle.getIDList()
            num_vehicles = len(vehicle_ids)

            if num_vehicles == 0:
                return {
                    "numVehicles": 0,
                    "avgSpeed": 0.0,
                    "totalDelay": 0.0,
                    "totalQueueLength": 0.0,
                    "avgWaitingTime": 0.0
                }

            # Calculate average speed
            total_speed = sum(traci.vehicle.getSpeed(v) for v in vehicle_ids)
            avg_speed = total_speed / num_vehicles if num_vehicles > 0 else 0.0

            # Calculate total waiting time (proxy for delay)
            total_waiting = sum(traci.vehicle.getWaitingTime(v) for v in vehicle_ids)

            # Calculate total queue length across all edges
            total_queue = sum(
                traci.edge.getLastStepHaltingNumber(e)
                for e in self.all_edges
            )

            return {
                "numVehicles": num_vehicles,
                "avgSpeed": round(avg_speed, 2),
                "totalDelay": round(total_waiting, 2),
                "totalQueueLength": total_queue,
                "avgWaitingTime": round(total_waiting / num_vehicles, 2) if num_vehicles > 0 else 0.0
            }

        except traci.TraCIException as e:
            print(f"Warning: Error collecting global metrics: {e}")
            return {
                "numVehicles": 0,
                "avgSpeed": 0.0,
                "totalDelay": 0.0,
                "totalQueueLength": 0,
                "avgWaitingTime": 0.0
            }

    def collect_edge_metrics(self, active_events: Dict[str, str]) -> List[Dict[str, Any]]:
        """Collect per-edge metrics."""
        edge_metrics = []

        for edge_id in self.all_edges:
            try:
                metrics = {
                    "edgeId": edge_id,
                    "avgSpeed": round(traci.edge.getLastStepMeanSpeed(edge_id), 2),
                    "flow": traci.edge.getLastStepVehicleNumber(edge_id),
                    "queueLen": traci.edge.getLastStepHaltingNumber(edge_id),
                    "occupancy": round(traci.edge.getLastStepOccupancy(edge_id), 2),
                    "waitingTime": round(traci.edge.getWaitingTime(edge_id), 2),
                    "regionTag": self.get_edge_region(edge_id),
                    "accidentFlag": edge_id in active_events and active_events[edge_id] == "accident",
                    "workzoneFlag": edge_id in active_events and active_events[edge_id] == "roadworks"
                }
                edge_metrics.append(metrics)

            except traci.TraCIException:
                continue

        return edge_metrics


class SimulationRunner:
    """Main simulation runner with TraCI control."""

    def __init__(
        self,
        config_path: str,
        use_gui: bool = False,
        use_firestore: bool = True,
        use_adaptive_control: bool = True,
        run_id: Optional[str] = None
    ):
        self.config = self._load_config(config_path)
        self.use_gui = use_gui
        self.use_firestore = use_firestore and FIRESTORE_AVAILABLE
        self.use_adaptive_control = use_adaptive_control and ADAPTIVE_CONTROLLER_AVAILABLE
        self.firestore: Optional[FirestoreClient] = None

        # IDs for this run
        self.scenario_id = str(uuid.uuid4())[:8]
        self.run_id = run_id or str(uuid.uuid4())[:8]

        # Events
        self.events: List[DynamicEvent] = []

        # Metrics collector
        self.metrics_collector = TrafficMetricsCollector(
            self.config.get("regions", {})
        )

        # Adaptive signal controller
        self.signal_controller: Optional[AdaptiveSignalController] = None
        if self.use_adaptive_control:
            self.signal_controller = AdaptiveSignalController(
                use_ml=self.config.get("useML", True),
                control_interval=self.config.get("controlInterval", 10)
            )

        # Results storage
        self.timeseries_data: List[Dict] = []

        # Real-time state storage (for streaming)
        self.current_state: Dict[str, Any] = {}

    def _load_config(self, config_path: str) -> Dict:
        """Load scenario configuration."""
        script_dir = Path(__file__).parent
        full_path = script_dir / config_path

        if not full_path.exists():
            # Try default
            full_path = script_dir / "config" / "default_scenario.json"

        if full_path.exists():
            with open(full_path) as f:
                return json.load(f)

        # Return minimal default config
        return {
            "name": "Default Scenario",
            "description": "Basic simulation",
            "simulationDuration": 3600,
            "stepLength": 1.0,
            "outputInterval": 60,
            "accident": {"enabled": False},
            "roadWorks": {"enabled": False},
            "regions": {}
        }

    def _setup_events(self):
        """Create dynamic events from config."""
        self.events = []

        # Accident event
        accident_cfg = self.config.get("accident", {})
        if accident_cfg.get("enabled", False):
            self.events.append(AccidentEvent(
                edge_id=accident_cfg["edgeId"],
                start_time=accident_cfg["startTime"],
                duration=accident_cfg["duration"],
                severity=accident_cfg.get("severity", "minor"),
                blocked_lanes=accident_cfg.get("blockedLanes", []),
                speed_reduction=accident_cfg.get("speedReduction", 0.5)
            ))

        # Road works event
        roadworks_cfg = self.config.get("roadWorks", {})
        if roadworks_cfg.get("enabled", False):
            self.events.append(RoadWorksEvent(
                edge_id=roadworks_cfg["edgeId"],
                start_time=roadworks_cfg["startTime"],
                duration=roadworks_cfg["duration"],
                blocked_lanes=roadworks_cfg.get("blockedLanes", []),
                speed_reduction=roadworks_cfg.get("speedReduction", 0.3)
            ))

    def _init_firestore(self):
        """Initialize Firestore connection and create scenario/run documents."""
        if not self.use_firestore:
            return

        try:
            self.firestore = FirestoreClient()

            # Create scenario document
            self.firestore.create_scenario(
                scenario_id=self.scenario_id,
                name=self.config.get("name", "Unnamed Scenario"),
                description=self.config.get("description", ""),
                parameters=self.config
            )

            # Create run document
            self.firestore.create_run(
                run_id=self.run_id,
                scenario_id=self.scenario_id
            )

            print(f"Firestore initialized - Scenario: {self.scenario_id}, Run: {self.run_id}")

        except Exception as e:
            print(f"Warning: Could not initialize Firestore: {e}")
            self.use_firestore = False

    def _start_sumo(self):
        """Start SUMO with TraCI."""
        script_dir = Path(__file__).parent
        sumo_cfg = script_dir / "chepauk.sumocfg"

        sumo_binary = "sumo-gui" if self.use_gui else "sumo"

        # Check if SUMO config exists
        if not sumo_cfg.exists():
            print("SUMO config not found. Generating network first...")
            import subprocess
            subprocess.run([sys.executable, str(script_dir / "generate_network.py")])

        cmd = [
            sumo_binary,
            "-c", str(sumo_cfg),
            "--step-length", str(self.config.get("stepLength", 1.0)),
            "--end", str(self.config.get("simulationDuration", 3600)),
            "--start", "true",
            "--quit-on-end", "true"
        ]

        print(f"Starting SUMO: {' '.join(cmd)}")
        traci.start(cmd)

        # Initialize metrics collector
        self.metrics_collector.initialize()

        # Initialize adaptive controller
        if self.signal_controller:
            self.signal_controller.initialize()
            print("Adaptive signal controller initialized")

    def _process_events(self, sim_time: float) -> Dict[str, str]:
        """Process dynamic events - activate/deactivate as needed."""
        active_events = {}

        for event in self.events:
            if event.should_activate(sim_time):
                event.activate()

            if event.should_deactivate(sim_time):
                event.deactivate()

            if event.is_active:
                event_type = "accident" if isinstance(event, AccidentEvent) else "roadworks"
                active_events[event.edge_id] = event_type

        return active_events

    def _collect_signal_states(self) -> List[Dict[str, Any]]:
        """Collect current signal states from all traffic lights."""
        signal_states = []
        try:
            tls_ids = traci.trafficlight.getIDList()
            for tls_id in tls_ids:
                state = {
                    "tlsId": tls_id,
                    "phase": traci.trafficlight.getPhase(tls_id),
                    "state": traci.trafficlight.getRedYellowGreenState(tls_id),
                    "nextSwitch": traci.trafficlight.getNextSwitch(tls_id) - traci.simulation.getTime()
                }
                signal_states.append(state)
        except traci.TraCIException:
            pass
        return signal_states

    def _collect_vehicle_positions(self) -> List[Dict[str, Any]]:
        """Collect current vehicle positions for visualization."""
        vehicles = []
        try:
            vehicle_ids = traci.vehicle.getIDList()
            # Limit to 500 vehicles for performance
            for vid in vehicle_ids[:500]:
                try:
                    pos = traci.vehicle.getPosition(vid)
                    vehicles.append({
                        "id": vid,
                        "x": pos[0],
                        "y": pos[1],
                        "speed": traci.vehicle.getSpeed(vid),
                        "angle": traci.vehicle.getAngle(vid),
                        "type": traci.vehicle.getTypeID(vid),
                        "edge": traci.vehicle.getRoadID(vid)
                    })
                except:
                    pass
        except traci.TraCIException:
            pass
        return vehicles

    def _collect_and_store_metrics(self, sim_time: float, active_events: Dict[str, str]):
        """Collect metrics and store to Firestore."""
        global_metrics = self.metrics_collector.collect_global_metrics()
        edge_metrics = self.metrics_collector.collect_edge_metrics(active_events)
        signal_states = self._collect_signal_states()
        vehicle_positions = self._collect_vehicle_positions()

        # Create timestep data
        timestep_data = {
            "t": sim_time,
            "timestamp": datetime.utcnow().isoformat(),
            "metricsGlobal": global_metrics,
            "metricsByEdge": edge_metrics,
            "signalStates": signal_states,
            "vehicleCount": len(vehicle_positions),
            "adaptiveControl": self.use_adaptive_control
        }

        # Update current state for real-time streaming
        self.current_state = {
            "t": sim_time,
            "metricsGlobal": global_metrics,
            "signalStates": signal_states,
            "vehicles": vehicle_positions,
            "activeEvents": list(active_events.keys())
        }

        # Store locally
        self.timeseries_data.append(timestep_data)

        # Store to Firestore
        if self.use_firestore and self.firestore:
            try:
                step_id = f"step_{int(sim_time):06d}"
                self.firestore.add_timeseries_data(
                    run_id=self.run_id,
                    step_id=step_id,
                    data=timestep_data
                )
            except Exception as e:
                print(f"Warning: Could not write to Firestore: {e}")

        # Log progress
        if int(sim_time) % 300 == 0:  # Every 5 minutes
            print(f"[{sim_time:.0f}s] Vehicles: {global_metrics['numVehicles']}, "
                  f"Avg Speed: {global_metrics['avgSpeed']:.1f} m/s, "
                  f"Queue: {global_metrics['totalQueueLength']}")

    def _finalize_run(self):
        """Finalize the simulation run."""
        if not self.timeseries_data:
            return

        # Calculate summary statistics
        all_speeds = [d["metricsGlobal"]["avgSpeed"] for d in self.timeseries_data]
        all_delays = [d["metricsGlobal"]["totalDelay"] for d in self.timeseries_data]
        all_queues = [d["metricsGlobal"]["totalQueueLength"] for d in self.timeseries_data]

        summary = {
            "avgSpeed": round(sum(all_speeds) / len(all_speeds), 2),
            "maxDelay": round(max(all_delays), 2),
            "avgDelay": round(sum(all_delays) / len(all_delays), 2),
            "maxQueueLength": max(all_queues),
            "avgQueueLength": round(sum(all_queues) / len(all_queues), 2),
            "totalTimesteps": len(self.timeseries_data),
            "adaptiveControl": self.use_adaptive_control,
            "mlModel": self.signal_controller.predictor.model_name if self.signal_controller and self.signal_controller.predictor else "none"
        }

        print("\n" + "=" * 50)
        print("SIMULATION SUMMARY")
        print("=" * 50)
        print(f"Average Speed: {summary['avgSpeed']:.2f} m/s")
        print(f"Max Delay: {summary['maxDelay']:.2f} s")
        print(f"Max Queue Length: {summary['maxQueueLength']}")
        print(f"Total Timesteps: {summary['totalTimesteps']}")

        # Update Firestore
        if self.use_firestore and self.firestore:
            try:
                self.firestore.update_run_status(
                    run_id=self.run_id,
                    status="completed",
                    summary=summary
                )
            except Exception as e:
                print(f"Warning: Could not update Firestore: {e}")

        # Save local backup
        output_file = Path(__file__).parent / f"output_{self.run_id}.json"
        with open(output_file, 'w') as f:
            json.dump({
                "runId": self.run_id,
                "scenarioId": self.scenario_id,
                "config": self.config,
                "summary": summary,
                "timeseries": self.timeseries_data
            }, f, indent=2)
        print(f"\nLocal backup saved: {output_file}")

    def run(self):
        """Execute the simulation."""
        print("\n" + "=" * 60)
        print("CHEPAUK TRAFFIC SIMULATION")
        print("=" * 60)
        print(f"Scenario: {self.config.get('name', 'Unknown')}")
        print(f"Duration: {self.config.get('simulationDuration', 3600)}s")
        print(f"Firestore: {'Enabled' if self.use_firestore else 'Disabled'}")
        print("=" * 60 + "\n")

        # Initialize
        self._setup_events()
        self._init_firestore()
        self._start_sumo()

        output_interval = self.config.get("outputInterval", 60)

        try:
            step = 0
            while traci.simulation.getMinExpectedNumber() > 0:
                # Advance simulation
                traci.simulationStep()
                sim_time = traci.simulation.getTime()

                # Process dynamic events
                active_events = self._process_events(sim_time)

                # Run adaptive signal control
                if self.signal_controller:
                    control_result = self.signal_controller.control_step(sim_time, active_events)
                    if control_result.get("decisions"):
                        for tls_id, decision in control_result["decisions"].items():
                            print(f"[{sim_time:.0f}s] TLS {tls_id}: {decision['action']} phase {decision.get('from_phase')} -> {decision.get('to_phase')}")

                # Collect metrics at intervals
                if step % output_interval == 0:
                    self._collect_and_store_metrics(sim_time, active_events)

                step += 1

                # Check end time
                if sim_time >= self.config.get("simulationDuration", 3600):
                    break

        except traci.TraCIException as e:
            print(f"TraCI Error: {e}")

        except KeyboardInterrupt:
            print("\nSimulation interrupted by user")

        finally:
            # Clean up
            try:
                traci.close()
            except:
                pass

            self._finalize_run()

        return self.run_id


def main():
    parser = argparse.ArgumentParser(description="Run Chepauk traffic simulation")
    parser.add_argument(
        "--config", "-c",
        default="config/default_scenario.json",
        help="Path to scenario config file"
    )
    parser.add_argument(
        "--gui", "-g",
        action="store_true",
        help="Run with SUMO GUI (opens visualization window)"
    )
    parser.add_argument(
        "--no-firestore",
        action="store_true",
        help="Disable Firestore integration"
    )
    parser.add_argument(
        "--no-adaptive",
        action="store_true",
        help="Disable ML-based adaptive signal control"
    )

    args = parser.parse_args()

    runner = SimulationRunner(
        config_path=args.config,
        use_gui=args.gui,
        use_firestore=not args.no_firestore,
        use_adaptive_control=not args.no_adaptive
    )

    run_id = runner.run()
    print(f"\nSimulation completed. Run ID: {run_id}")


if __name__ == "__main__":
    main()
