"""
Traffic Prediction Models

This module provides the inference interface for traffic prediction.
The architecture supports multiple model backends:
1. MovingAverageModel - Simple baseline (default)
2. LSTMModel - PyTorch LSTM-based temporal model
3. (Future) GNNModel - Graph Neural Network for spatial-temporal prediction

To swap models, change the MODEL_TYPE constant or implement a new model
class following the BaseModel interface.
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# Try to import PyTorch (optional)
try:
    import torch
    import torch.nn as nn
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    print("PyTorch not available. Using baseline model only.")


# Model type selection
MODEL_TYPE = os.environ.get("TRAFFIC_MODEL_TYPE", "moving_average")  # or "lstm"


class BaseModel(ABC):
    """Abstract base class for traffic prediction models."""

    @abstractmethod
    def predict(
        self,
        speeds: np.ndarray,
        queue_lens: np.ndarray,
        event_flags: np.ndarray,
        horizon_steps: int
    ) -> Dict[str, np.ndarray]:
        """
        Predict future traffic metrics.

        Args:
            speeds: Historical speed values (shape: [seq_len])
            queue_lens: Historical queue lengths (shape: [seq_len])
            event_flags: Historical event flags (shape: [seq_len])
            horizon_steps: Number of future steps to predict

        Returns:
            Dict with 'speeds' and 'queue_lens' arrays of shape [horizon_steps]
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Model name for identification."""
        pass


class MovingAverageModel(BaseModel):
    """
    Simple moving average baseline model.

    This provides a reasonable baseline for short-term prediction.
    For longer horizons or more complex patterns, use the LSTM model.
    """

    def __init__(self, window_size: int = 5):
        self.window_size = window_size

    @property
    def name(self) -> str:
        return "MovingAverage"

    def predict(
        self,
        speeds: np.ndarray,
        queue_lens: np.ndarray,
        event_flags: np.ndarray,
        horizon_steps: int
    ) -> Dict[str, np.ndarray]:
        """
        Predict using exponentially weighted moving average.

        Incorporates trend and event impact adjustments.
        """
        # Calculate weighted moving average
        weights = np.exp(np.linspace(-1, 0, min(self.window_size, len(speeds))))
        weights = weights / weights.sum()

        recent_speeds = speeds[-self.window_size:] if len(speeds) >= self.window_size else speeds
        recent_queues = queue_lens[-self.window_size:] if len(queue_lens) >= self.window_size else queue_lens

        # Pad if necessary
        if len(recent_speeds) < self.window_size:
            pad_size = self.window_size - len(recent_speeds)
            recent_speeds = np.pad(recent_speeds, (pad_size, 0), mode='edge')
            recent_queues = np.pad(recent_queues, (pad_size, 0), mode='edge')
            weights = np.exp(np.linspace(-1, 0, len(recent_speeds)))
            weights = weights / weights.sum()

        # Base predictions
        base_speed = np.average(recent_speeds, weights=weights)
        base_queue = np.average(recent_queues, weights=weights)

        # Calculate trend (simple linear)
        if len(speeds) >= 3:
            speed_trend = (speeds[-1] - speeds[-3]) / 2
            queue_trend = (queue_lens[-1] - queue_lens[-3]) / 2
        else:
            speed_trend = 0
            queue_trend = 0

        # Check for active event
        has_active_event = event_flags[-1] if len(event_flags) > 0 else False

        # Generate predictions
        pred_speeds = []
        pred_queues = []

        for i in range(horizon_steps):
            # Apply trend with decay
            trend_decay = np.exp(-0.1 * i)

            pred_speed = base_speed + speed_trend * trend_decay * (i + 1)
            pred_queue = base_queue + queue_trend * trend_decay * (i + 1)

            # Event impact: if event is active, expect continued degradation
            if has_active_event:
                pred_speed *= 0.85  # 15% speed reduction
                pred_queue *= 1.3   # 30% queue increase

            # Clamp to reasonable ranges
            pred_speed = max(0.0, min(pred_speed, 50.0))  # 0-50 m/s
            pred_queue = max(0.0, min(pred_queue, 100.0))  # 0-100 vehicles

            pred_speeds.append(pred_speed)
            pred_queues.append(pred_queue)

        return {
            "speeds": np.array(pred_speeds),
            "queue_lens": np.array(pred_queues)
        }


if PYTORCH_AVAILABLE:
    class LSTMNetwork(nn.Module):
        """PyTorch LSTM network for sequence prediction."""

        def __init__(
            self,
            input_size: int = 3,  # speed, queue, event_flag
            hidden_size: int = 64,
            num_layers: int = 2,
            output_size: int = 2,  # speed, queue
            dropout: float = 0.2
        ):
            super().__init__()

            self.hidden_size = hidden_size
            self.num_layers = num_layers

            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0
            )

            self.fc = nn.Sequential(
                nn.Linear(hidden_size, hidden_size // 2),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_size // 2, output_size)
            )

        def forward(self, x):
            """
            Forward pass.

            Args:
                x: Input tensor of shape [batch, seq_len, input_size]

            Returns:
                Output tensor of shape [batch, output_size]
            """
            lstm_out, _ = self.lstm(x)
            # Use last timestep output
            last_out = lstm_out[:, -1, :]
            return self.fc(last_out)


    class LSTMModel(BaseModel):
        """
        LSTM-based traffic prediction model.

        Uses a 2-layer LSTM with attention-like mechanism for
        temporal traffic prediction.
        """

        def __init__(self, model_path: Optional[str] = None):
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.network = LSTMNetwork().to(self.device)

            # Load pre-trained weights if available
            if model_path and Path(model_path).exists():
                self.network.load_state_dict(torch.load(model_path, map_location=self.device))
                self.network.eval()
                print(f"Loaded LSTM model from {model_path}")
            else:
                print("Using untrained LSTM model (random weights)")

        @property
        def name(self) -> str:
            return "LSTM"

        def predict(
            self,
            speeds: np.ndarray,
            queue_lens: np.ndarray,
            event_flags: np.ndarray,
            horizon_steps: int
        ) -> Dict[str, np.ndarray]:
            """Predict using LSTM model."""
            self.network.eval()

            # Normalize inputs
            speed_mean, speed_std = 10.0, 5.0
            queue_mean, queue_std = 5.0, 3.0

            norm_speeds = (speeds - speed_mean) / speed_std
            norm_queues = (queue_lens - queue_mean) / queue_std
            event_float = event_flags.astype(np.float32)

            # Stack features
            features = np.stack([norm_speeds, norm_queues, event_float], axis=-1)

            # Convert to tensor
            x = torch.FloatTensor(features).unsqueeze(0).to(self.device)

            pred_speeds = []
            pred_queues = []

            with torch.no_grad():
                for _ in range(horizon_steps):
                    # Predict next step
                    output = self.network(x)

                    # Denormalize
                    pred_speed = output[0, 0].item() * speed_std + speed_mean
                    pred_queue = output[0, 1].item() * queue_std + queue_mean

                    # Clamp
                    pred_speed = max(0.0, min(pred_speed, 50.0))
                    pred_queue = max(0.0, min(pred_queue, 100.0))

                    pred_speeds.append(pred_speed)
                    pred_queues.append(pred_queue)

                    # Update input sequence (shift and append prediction)
                    new_features = torch.FloatTensor([[
                        (pred_speed - speed_mean) / speed_std,
                        (pred_queue - queue_mean) / queue_std,
                        event_float[-1]  # Assume event continues
                    ]]).unsqueeze(0).to(self.device)

                    x = torch.cat([x[:, 1:, :], new_features], dim=1)

            return {
                "speeds": np.array(pred_speeds),
                "queue_lens": np.array(pred_queues)
            }


class TrafficPredictor:
    """
    Main inference interface for traffic prediction.

    This class wraps the underlying model and provides a clean API
    for making predictions. The model can be swapped by changing
    the MODEL_TYPE environment variable.
    """

    def __init__(self, model_type: Optional[str] = None):
        """
        Initialize the predictor.

        Args:
            model_type: Override model type (default uses MODEL_TYPE env var)
        """
        model_type = model_type or MODEL_TYPE

        if model_type == "lstm" and PYTORCH_AVAILABLE:
            model_path = Path(__file__).parent / "weights" / "lstm_model.pt"
            self.model = LSTMModel(str(model_path) if model_path.exists() else None)
        else:
            self.model = MovingAverageModel()

        print(f"TrafficPredictor initialized with {self.model.name} model")

    @property
    def model_name(self) -> str:
        """Get the name of the underlying model."""
        return self.model.name

    def predict(
        self,
        edge_histories: List[Dict[str, Any]],
        horizon_seconds: int = 300,
        step_seconds: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Predict traffic for multiple edges.

        Args:
            edge_histories: List of edge history dicts with keys:
                - edgeId: str
                - speeds: List[float]
                - queueLens: List[float]
                - eventFlags: List[bool] (optional)
            horizon_seconds: Total prediction horizon in seconds
            step_seconds: Time step for predictions in seconds

        Returns:
            List of prediction dicts with keys:
                - edgeId: str
                - t: float (time offset in seconds)
                - speed: float
                - queueLen: float
        """
        horizon_steps = horizon_seconds // step_seconds
        predictions = []

        for edge_data in edge_histories:
            edge_id = edge_data.get("edgeId") or edge_data.get("edge_id", "unknown")

            # Extract arrays
            speeds = np.array(edge_data.get("speeds", []))
            queue_lens = np.array(edge_data.get("queueLens") or edge_data.get("queue_lens", []))
            event_flags = np.array(edge_data.get("eventFlags") or edge_data.get("event_flags", []), dtype=bool)

            # Ensure minimum history
            if len(speeds) < 2:
                speeds = np.array([10.0, 10.0])  # Default
            if len(queue_lens) < 2:
                queue_lens = np.array([2.0, 2.0])  # Default
            if len(event_flags) < len(speeds):
                event_flags = np.zeros(len(speeds), dtype=bool)

            # Get predictions
            result = self.model.predict(speeds, queue_lens, event_flags, horizon_steps)

            # Format output
            for i in range(horizon_steps):
                predictions.append({
                    "edgeId": edge_id,
                    "t": (i + 1) * step_seconds,
                    "speed": round(float(result["speeds"][i]), 2),
                    "queueLen": round(float(result["queue_lens"][i]), 1)
                })

        return predictions

    def predict_single_edge(
        self,
        edge_id: str,
        speeds: List[float],
        queue_lens: List[float],
        event_flags: Optional[List[bool]] = None,
        horizon_seconds: int = 300,
        step_seconds: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Convenience method for single edge prediction.
        """
        return self.predict(
            edge_histories=[{
                "edgeId": edge_id,
                "speeds": speeds,
                "queueLens": queue_lens,
                "eventFlags": event_flags or []
            }],
            horizon_seconds=horizon_seconds,
            step_seconds=step_seconds
        )


# ============================================================================
# FUTURE: Graph Neural Network Model
# ============================================================================

# TODO: Implement GNN model for spatial-temporal traffic prediction
#
# class GNNModel(BaseModel):
#     """
#     Graph Neural Network for traffic prediction.
#
#     This model captures both temporal dependencies (via LSTM/Transformer)
#     and spatial dependencies (via message passing on the road network graph).
#
#     Architecture:
#     1. Node features: speed, queue, occupancy, event flags
#     2. Edge features: road connectivity, distance
#     3. Temporal encoder: LSTM or Transformer
#     4. Spatial encoder: GAT or GCN layers
#     5. Decoder: MLP for per-node predictions
#     """
#     pass
