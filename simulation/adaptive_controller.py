#!/usr/bin/env python3
"""
Adaptive Traffic Light Controller with ML Integration

This module implements intelligent traffic light control using:
1. Max-pressure algorithm for queue-based optimization
2. ML predictions for proactive signal timing
3. Real-time adaptation based on traffic conditions

The controller integrates with SUMO via TraCI to dynamically
adjust signal phases based on current and predicted traffic states.
"""

import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field
import numpy as np

# Add parent path for ML model import
sys.path.append(str(Path(__file__).parent.parent / "backend"))

try:
    from ml_model.model import TrafficPredictor
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("WARNING: ML model not available. Using rule-based control only.")

# TraCI import (will be available when running with simulation)
try:
    import traci
    TRACI_AVAILABLE = True
except ImportError:
    TRACI_AVAILABLE = False


@dataclass
class TrafficLightConfig:
    """Configuration for a single traffic light."""
    tls_id: str
    incoming_edges: List[str] = field(default_factory=list)
    outgoing_edges: List[str] = field(default_factory=list)
    phase_count: int = 0
    min_green: float = 5.0
    max_green: float = 60.0
    yellow_time: float = 3.0


@dataclass
class TrafficState:
    """Current traffic state for an edge/lane."""
    edge_id: str
    avg_speed: float = 0.0
    queue_length: int = 0
    vehicle_count: int = 0
    waiting_time: float = 0.0
    occupancy: float = 0.0
    has_event: bool = False


@dataclass
class SignalState:
    """Current state of a traffic signal."""
    tls_id: str
    current_phase: int
    phase_state: str  # e.g., "GGrrGGrr"
    time_in_phase: float
    next_switch: float


class AdaptiveSignalController:
    """
    Adaptive traffic signal controller using ML predictions.

    This controller implements a hybrid approach:
    1. Max-pressure algorithm: Prioritizes phases with highest queue pressure
    2. ML predictions: Anticipates future traffic for proactive control
    3. Event handling: Adapts to accidents and road works
    """

    # Traffic light configurations for Chepauk network
    TLS_CONFIG = {
        "junction_main": TrafficLightConfig(
            tls_id="junction_main",
            incoming_edges=["anna_salai_sb", "anna_salai_nb", "wallajah_eb", "wallajah_wb", "stadium_exit_s", "uni_entrance_out"],
            outgoing_edges=["anna_salai_sb2", "anna_salai_nb2", "wallajah_eb2", "wallajah_wb2", "stadium_exit_s_rev", "uni_entrance_in"],
            phase_count=13,
            min_green=5.0,
            max_green=50.0
        ),
        "junction_north": TrafficLightConfig(
            tls_id="junction_north",
            incoming_edges=["anna_salai_nb2", "stadium_approach_n_rev", "uni_north_conn"],
            outgoing_edges=["anna_salai_sb", "stadium_approach_n", "uni_north_conn_rev"],
            phase_count=9,
            min_green=5.0,
            max_green=50.0
        ),
        "stadium_north": TrafficLightConfig(
            tls_id="stadium_north",
            incoming_edges=["stadium_internal_rev", "stadium_approach_n"],
            outgoing_edges=["stadium_approach_n_rev", "stadium_internal"],
            phase_count=3,
            min_green=5.0,
            max_green=50.0
        ),
        "stadium_south": TrafficLightConfig(
            tls_id="stadium_south",
            incoming_edges=["stadium_internal", "stadium_exit_s_rev", "stadium_east_entry"],
            outgoing_edges=["stadium_exit_s", "stadium_internal_rev", "stadium_east_exit"],
            phase_count=6,
            min_green=5.0,
            max_green=50.0
        ),
        "uni_east": TrafficLightConfig(
            tls_id="uni_east",
            incoming_edges=["uni_south_to_east", "uni_entrance_in", "uni_from_east"],
            outgoing_edges=["uni_east_to_south", "uni_entrance_out", "uni_to_east"],
            phase_count=6,
            min_green=5.0,
            max_green=50.0
        ),
        "uni_north": TrafficLightConfig(
            tls_id="uni_north",
            incoming_edges=["uni_to_east", "uni_north_conn_rev", "uni_internal_sn", "kamarajar_sb"],
            outgoing_edges=["uni_from_east", "uni_north_conn", "uni_internal_ns", "kamarajar_sb2"],
            phase_count=9,
            min_green=5.0,
            max_green=50.0
        ),
        "uni_south": TrafficLightConfig(
            tls_id="uni_south",
            incoming_edges=["uni_internal_ns", "uni_east_to_south", "kamarajar_nb"],
            outgoing_edges=["uni_internal_sn", "uni_south_to_east", "kamarajar_nb2"],
            phase_count=9,
            min_green=5.0,
            max_green=50.0
        ),
    }

    def __init__(
        self,
        use_ml: bool = True,
        prediction_horizon: int = 300,  # 5 minutes
        control_interval: int = 10,      # Control decision every 10 seconds
        pressure_weight: float = 0.6,    # Weight for queue pressure
        prediction_weight: float = 0.4,  # Weight for ML predictions
    ):
        self.use_ml = use_ml and ML_AVAILABLE
        self.prediction_horizon = prediction_horizon
        self.control_interval = control_interval
        self.pressure_weight = pressure_weight
        self.prediction_weight = prediction_weight

        # Initialize ML predictor
        self.predictor: Optional[TrafficPredictor] = None
        if self.use_ml:
            try:
                self.predictor = TrafficPredictor()
                print(f"Adaptive controller initialized with {self.predictor.model_name} model")
            except Exception as e:
                print(f"WARNING: Could not initialize ML predictor: {e}")
                self.use_ml = False

        # State tracking
        self.traffic_history: Dict[str, List[TrafficState]] = defaultdict(list)
        self.signal_states: Dict[str, SignalState] = {}
        self.last_control_time: float = 0.0
        self.phase_timers: Dict[str, float] = {}

        # Active events (accidents, road works)
        self.active_events: Dict[str, str] = {}

        # Performance metrics
        self.total_waiting_time: float = 0.0
        self.decisions_made: int = 0

    def initialize(self):
        """Initialize controller after SUMO connection."""
        if not TRACI_AVAILABLE:
            print("WARNING: TraCI not available. Controller in offline mode.")
            return

        # Get all traffic lights
        tls_ids = traci.trafficlight.getIDList()
        print(f"Found {len(tls_ids)} traffic lights: {tls_ids}")

        # Initialize signal states
        for tls_id in tls_ids:
            if tls_id in self.TLS_CONFIG:
                state = traci.trafficlight.getRedYellowGreenState(tls_id)
                phase = traci.trafficlight.getPhase(tls_id)
                self.signal_states[tls_id] = SignalState(
                    tls_id=tls_id,
                    current_phase=phase,
                    phase_state=state,
                    time_in_phase=0.0,
                    next_switch=traci.trafficlight.getNextSwitch(tls_id)
                )
                self.phase_timers[tls_id] = 0.0

    def update_traffic_state(self, edge_id: str, active_events: Dict[str, str]) -> TrafficState:
        """Collect current traffic state for an edge."""
        if not TRACI_AVAILABLE:
            return TrafficState(edge_id=edge_id)

        try:
            state = TrafficState(
                edge_id=edge_id,
                avg_speed=traci.edge.getLastStepMeanSpeed(edge_id),
                queue_length=traci.edge.getLastStepHaltingNumber(edge_id),
                vehicle_count=traci.edge.getLastStepVehicleNumber(edge_id),
                waiting_time=traci.edge.getWaitingTime(edge_id),
                occupancy=traci.edge.getLastStepOccupancy(edge_id),
                has_event=edge_id in active_events
            )

            # Update history
            self.traffic_history[edge_id].append(state)
            # Keep only last 20 samples (for ML prediction)
            if len(self.traffic_history[edge_id]) > 20:
                self.traffic_history[edge_id] = self.traffic_history[edge_id][-20:]

            return state

        except Exception as e:
            return TrafficState(edge_id=edge_id)

    def calculate_phase_pressure(self, tls_id: str) -> Dict[int, float]:
        """
        Calculate pressure for each phase using max-pressure algorithm.

        Pressure = sum of (incoming queue) - sum of (outgoing capacity)
        Higher pressure phases should get priority.
        """
        config = self.TLS_CONFIG.get(tls_id)
        if not config:
            return {}

        pressures = {}

        # Get current program
        try:
            program = traci.trafficlight.getAllProgramLogics(tls_id)[0]
            phases = program.phases

            for phase_idx, phase in enumerate(phases):
                # Skip yellow and all-red phases
                if 'G' not in phase.state and 'g' not in phase.state:
                    pressures[phase_idx] = -1000  # Heavily penalize non-green phases
                    continue

                pressure = 0.0

                # Calculate pressure from incoming edges with green
                for i, incoming_edge in enumerate(config.incoming_edges):
                    if incoming_edge in self.traffic_history and self.traffic_history[incoming_edge]:
                        latest = self.traffic_history[incoming_edge][-1]

                        # Queue-based pressure
                        queue_pressure = latest.queue_length * 2.0  # Weight queued vehicles

                        # Speed-based pressure (slow = high pressure)
                        speed_pressure = max(0, 13.89 - latest.avg_speed) / 13.89 * 5

                        # Event boost (prioritize clearing accidents)
                        event_boost = 10.0 if latest.has_event else 0.0

                        pressure += queue_pressure + speed_pressure + event_boost

                pressures[phase_idx] = pressure

        except Exception as e:
            pass

        return pressures

    def get_ml_predictions(self, tls_id: str) -> Dict[str, List[float]]:
        """Get ML predictions for incoming edges of a traffic light."""
        if not self.use_ml or not self.predictor:
            return {}

        config = self.TLS_CONFIG.get(tls_id)
        if not config:
            return {}

        predictions = {}
        edge_histories = []

        for edge_id in config.incoming_edges:
            if edge_id in self.traffic_history and len(self.traffic_history[edge_id]) >= 3:
                history = self.traffic_history[edge_id]
                edge_histories.append({
                    "edgeId": edge_id,
                    "speeds": [s.avg_speed for s in history],
                    "queueLens": [s.queue_length for s in history],
                    "eventFlags": [s.has_event for s in history]
                })

        if edge_histories:
            try:
                raw_predictions = self.predictor.predict(
                    edge_histories,
                    horizon_seconds=self.prediction_horizon,
                    step_seconds=60
                )

                # Organize by edge
                for pred in raw_predictions:
                    edge_id = pred["edgeId"]
                    if edge_id not in predictions:
                        predictions[edge_id] = {"speeds": [], "queues": []}
                    predictions[edge_id]["speeds"].append(pred["speed"])
                    predictions[edge_id]["queues"].append(pred["queueLen"])

            except Exception as e:
                pass

        return predictions

    def calculate_optimal_phase(self, tls_id: str) -> Tuple[int, float]:
        """
        Calculate the optimal phase and duration for a traffic light.

        Returns:
            Tuple of (optimal_phase_index, recommended_duration)
        """
        config = self.TLS_CONFIG.get(tls_id)
        if not config:
            return (0, 30.0)

        # Get pressure-based scores
        pressures = self.calculate_phase_pressure(tls_id)

        # Get ML predictions
        predictions = self.get_ml_predictions(tls_id)

        # Combine scores
        combined_scores = {}

        for phase_idx, pressure in pressures.items():
            # Base score from pressure
            score = pressure * self.pressure_weight

            # Add prediction-based adjustment
            if predictions:
                # If predictions show increasing queue, boost phase priority
                for edge_id, preds in predictions.items():
                    if preds["queues"]:
                        future_queue_trend = np.mean(preds["queues"][-3:]) - np.mean(preds["queues"][:3]) if len(preds["queues"]) >= 3 else 0
                        score += future_queue_trend * self.prediction_weight

            combined_scores[phase_idx] = score

        # Find best phase
        if combined_scores:
            best_phase = max(combined_scores, key=combined_scores.get)
            best_score = combined_scores[best_phase]

            # Calculate duration based on pressure
            base_duration = 20.0
            duration = base_duration + (best_score / 10.0) * 10.0
            duration = max(config.min_green, min(config.max_green, duration))

            return (best_phase, duration)

        return (0, config.min_green)

    def should_switch_phase(self, tls_id: str, current_time: float) -> bool:
        """Determine if a phase switch is needed."""
        config = self.TLS_CONFIG.get(tls_id)
        if not config or tls_id not in self.signal_states:
            return False

        signal_state = self.signal_states[tls_id]
        time_in_phase = self.phase_timers.get(tls_id, 0.0)

        # Check minimum green time
        if time_in_phase < config.min_green:
            return False

        # Check maximum green time
        if time_in_phase >= config.max_green:
            return True

        # Get current pressures
        pressures = self.calculate_phase_pressure(tls_id)
        current_pressure = pressures.get(signal_state.current_phase, 0)

        # Find maximum pressure for other phases
        other_pressures = [p for idx, p in pressures.items() if idx != signal_state.current_phase]
        max_other_pressure = max(other_pressures) if other_pressures else 0

        # Switch if another phase has significantly higher pressure
        pressure_threshold = current_pressure * 1.5 + 5.0
        if max_other_pressure > pressure_threshold:
            return True

        return False

    def control_step(self, sim_time: float, active_events: Dict[str, str]) -> Dict[str, Any]:
        """
        Execute one control step - called every simulation step.

        Returns control decisions and current states.
        """
        self.active_events = active_events

        # Only make control decisions at intervals
        if sim_time - self.last_control_time < self.control_interval:
            # Still update phase timers
            for tls_id in self.phase_timers:
                self.phase_timers[tls_id] += 1.0
            return self._get_current_state()

        self.last_control_time = sim_time
        self.decisions_made += 1

        decisions = {}

        for tls_id, config in self.TLS_CONFIG.items():
            # Update traffic states for all incoming edges
            for edge_id in config.incoming_edges:
                try:
                    self.update_traffic_state(edge_id, active_events)
                except:
                    pass

            # Check if phase switch is needed
            if self.should_switch_phase(tls_id, sim_time):
                optimal_phase, duration = self.calculate_optimal_phase(tls_id)

                try:
                    # Get current state
                    current_phase = traci.trafficlight.getPhase(tls_id)

                    # Only switch if different from current
                    if optimal_phase != current_phase:
                        # Set new phase
                        traci.trafficlight.setPhase(tls_id, optimal_phase)

                        # Update our tracking
                        if tls_id in self.signal_states:
                            self.signal_states[tls_id].current_phase = optimal_phase
                            self.signal_states[tls_id].phase_state = traci.trafficlight.getRedYellowGreenState(tls_id)

                        self.phase_timers[tls_id] = 0.0

                        decisions[tls_id] = {
                            "action": "switch",
                            "from_phase": current_phase,
                            "to_phase": optimal_phase,
                            "duration": duration
                        }

                except Exception as e:
                    pass

            # Update phase timer
            self.phase_timers[tls_id] = self.phase_timers.get(tls_id, 0.0) + self.control_interval

        return {
            "time": sim_time,
            "decisions": decisions,
            "signal_states": self._get_signal_states(),
            "traffic_states": self._get_traffic_states()
        }

    def _get_current_state(self) -> Dict[str, Any]:
        """Get current state without making decisions."""
        return {
            "signal_states": self._get_signal_states(),
            "traffic_states": self._get_traffic_states()
        }

    def _get_signal_states(self) -> List[Dict[str, Any]]:
        """Get current signal states for all traffic lights."""
        states = []

        for tls_id in self.TLS_CONFIG.keys():
            try:
                state = {
                    "tlsId": tls_id,
                    "phase": traci.trafficlight.getPhase(tls_id),
                    "state": traci.trafficlight.getRedYellowGreenState(tls_id),
                    "timeInPhase": self.phase_timers.get(tls_id, 0.0),
                    "nextSwitch": traci.trafficlight.getNextSwitch(tls_id)
                }
                states.append(state)
            except:
                pass

        return states

    def _get_traffic_states(self) -> Dict[str, Dict[str, Any]]:
        """Get current traffic states for monitored edges."""
        states = {}

        for edge_id, history in self.traffic_history.items():
            if history:
                latest = history[-1]
                states[edge_id] = {
                    "avgSpeed": latest.avg_speed,
                    "queueLength": latest.queue_length,
                    "vehicleCount": latest.vehicle_count,
                    "waitingTime": latest.waiting_time,
                    "occupancy": latest.occupancy,
                    "hasEvent": latest.has_event
                }

        return states

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get controller performance metrics."""
        return {
            "decisionssMade": self.decisions_made,
            "useML": self.use_ml,
            "modelName": self.predictor.model_name if self.predictor else "none"
        }


# Standalone test
if __name__ == "__main__":
    print("Adaptive Signal Controller - Test Mode")
    controller = AdaptiveSignalController(use_ml=True)
    print(f"Controller initialized. ML available: {controller.use_ml}")
    print(f"Traffic light configs: {list(controller.TLS_CONFIG.keys())}")
