#!/usr/bin/env python3
"""
Training Script for Traffic Prediction Model

This script trains the LSTM model on historical traffic data from Firestore
or local JSON exports.

Usage:
    python train_model.py --data-source local --data-path ../simulation/output_*.json
    python train_model.py --data-source firestore --epochs 100

The trained model is saved to weights/lstm_model.pt
"""

import argparse
import json
import os
import sys
from glob import glob
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

# Try to import PyTorch
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, Dataset, random_split
except ImportError:
    print("ERROR: PyTorch is required for training. Install with: pip install torch")
    sys.exit(1)

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml_model.model import LSTMNetwork


class TrafficDataset(Dataset):
    """PyTorch Dataset for traffic time-series data."""

    def __init__(
        self,
        data: List[Dict],
        seq_length: int = 12,
        pred_horizon: int = 1
    ):
        """
        Initialize dataset.

        Args:
            data: List of timestep dicts with metricsByEdge
            seq_length: Number of historical timesteps for input
            pred_horizon: Number of steps ahead to predict
        """
        self.seq_length = seq_length
        self.pred_horizon = pred_horizon

        # Extract per-edge time series
        self.samples = self._prepare_samples(data)
        print(f"Created dataset with {len(self.samples)} samples")

    def _prepare_samples(self, data: List[Dict]) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Convert raw data to (X, Y) sample pairs."""
        samples = []

        # Group data by edge
        edge_data: Dict[str, List[Dict]] = {}

        for timestep in data:
            for edge_metrics in timestep.get("metricsByEdge", []):
                edge_id = edge_metrics["edgeId"]
                if edge_id not in edge_data:
                    edge_data[edge_id] = []

                edge_data[edge_id].append({
                    "t": timestep.get("t", 0),
                    "speed": edge_metrics.get("avgSpeed", 0),
                    "queue": edge_metrics.get("queueLen", 0),
                    "event": 1.0 if (edge_metrics.get("accidentFlag") or
                                    edge_metrics.get("workzoneFlag")) else 0.0
                })

        # Create sliding window samples for each edge
        for edge_id, metrics in edge_data.items():
            if len(metrics) < self.seq_length + self.pred_horizon:
                continue

            # Sort by time
            metrics.sort(key=lambda x: x["t"])

            # Normalize
            speeds = np.array([m["speed"] for m in metrics])
            queues = np.array([m["queue"] for m in metrics])
            events = np.array([m["event"] for m in metrics])

            speed_mean, speed_std = speeds.mean(), speeds.std() + 1e-6
            queue_mean, queue_std = queues.mean(), queues.std() + 1e-6

            norm_speeds = (speeds - speed_mean) / speed_std
            norm_queues = (queues - queue_mean) / queue_std

            # Create samples
            for i in range(len(metrics) - self.seq_length - self.pred_horizon + 1):
                # Input sequence
                x_speeds = norm_speeds[i:i + self.seq_length]
                x_queues = norm_queues[i:i + self.seq_length]
                x_events = events[i:i + self.seq_length]

                X = np.stack([x_speeds, x_queues, x_events], axis=-1)

                # Target (next step)
                target_idx = i + self.seq_length + self.pred_horizon - 1
                Y = np.array([
                    norm_speeds[target_idx],
                    norm_queues[target_idx]
                ])

                samples.append((X.astype(np.float32), Y.astype(np.float32)))

        return samples

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        X, Y = self.samples[idx]
        return torch.FloatTensor(X), torch.FloatTensor(Y)


def load_local_data(data_paths: List[str]) -> List[Dict]:
    """Load data from local JSON files."""
    all_data = []

    for pattern in data_paths:
        for filepath in glob(pattern):
            print(f"Loading: {filepath}")
            with open(filepath) as f:
                data = json.load(f)

            timeseries = data.get("timeseries", [])
            all_data.extend(timeseries)

    print(f"Loaded {len(all_data)} timesteps from local files")
    return all_data


def load_firestore_data(run_ids: List[str] = None, limit: int = 10) -> List[Dict]:
    """Load data from Firestore."""
    try:
        from firestore_client import FirestoreClient
        client = FirestoreClient()
    except Exception as e:
        print(f"ERROR: Could not connect to Firestore: {e}")
        return []

    all_data = []

    if run_ids:
        # Load specific runs
        for run_id in run_ids:
            timeseries = client.get_timeseries(run_id, limit=1000)
            all_data.extend(timeseries)
    else:
        # Load from most recent completed runs
        runs = client.list_runs(status="completed", limit=limit)
        for run in runs:
            timeseries = client.get_timeseries(run["id"], limit=1000)
            all_data.extend(timeseries)

    print(f"Loaded {len(all_data)} timesteps from Firestore")
    return all_data


def train_model(
    data: List[Dict],
    epochs: int = 50,
    batch_size: int = 32,
    learning_rate: float = 0.001,
    seq_length: int = 12,
    val_split: float = 0.2
):
    """Train the LSTM model."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Create dataset
    dataset = TrafficDataset(data, seq_length=seq_length)

    if len(dataset) < 10:
        print("ERROR: Not enough data for training. Need at least 10 samples.")
        return None

    # Split into train/val
    val_size = int(len(dataset) * val_split)
    train_size = len(dataset) - val_size
    train_dataset, val_dataset = random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size)

    print(f"Train samples: {train_size}, Validation samples: {val_size}")

    # Initialize model
    model = LSTMNetwork(
        input_size=3,
        hidden_size=64,
        num_layers=2,
        output_size=2,
        dropout=0.2
    ).to(device)

    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

    best_val_loss = float('inf')
    best_model_state = None

    # Training loop
    for epoch in range(epochs):
        # Train
        model.train()
        train_loss = 0.0

        for X, Y in train_loader:
            X, Y = X.to(device), Y.to(device)

            optimizer.zero_grad()
            output = model(X)
            loss = criterion(output, Y)
            loss.backward()

            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

            optimizer.step()
            train_loss += loss.item()

        train_loss /= len(train_loader)

        # Validate
        model.eval()
        val_loss = 0.0

        with torch.no_grad():
            for X, Y in val_loader:
                X, Y = X.to(device), Y.to(device)
                output = model(X)
                loss = criterion(output, Y)
                val_loss += loss.item()

        val_loss /= len(val_loader)
        scheduler.step(val_loss)

        # Save best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_model_state = model.state_dict().copy()

        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"Epoch {epoch + 1}/{epochs} - Train Loss: {train_loss:.6f}, Val Loss: {val_loss:.6f}")

    # Restore best model
    if best_model_state:
        model.load_state_dict(best_model_state)

    print(f"\nTraining complete. Best validation loss: {best_val_loss:.6f}")
    return model


def save_model(model, output_path: str):
    """Save model weights."""
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    torch.save(model.state_dict(), output_path)
    print(f"Model saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Train traffic prediction model")
    parser.add_argument(
        "--data-source",
        choices=["local", "firestore"],
        default="local",
        help="Data source type"
    )
    parser.add_argument(
        "--data-path",
        nargs="+",
        default=["../simulation/output_*.json"],
        help="Glob patterns for local data files"
    )
    parser.add_argument(
        "--run-ids",
        nargs="+",
        help="Specific Firestore run IDs to use"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=50,
        help="Number of training epochs"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Training batch size"
    )
    parser.add_argument(
        "--seq-length",
        type=int,
        default=12,
        help="Input sequence length"
    )
    parser.add_argument(
        "--output",
        default="weights/lstm_model.pt",
        help="Output model path"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Traffic Prediction Model Training")
    print("=" * 60)

    # Load data
    if args.data_source == "local":
        data = load_local_data(args.data_path)
    else:
        data = load_firestore_data(args.run_ids)

    if not data:
        print("ERROR: No data available for training")
        sys.exit(1)

    # Train model
    model = train_model(
        data,
        epochs=args.epochs,
        batch_size=args.batch_size,
        seq_length=args.seq_length
    )

    if model:
        save_model(model, args.output)

    print("\nDone!")


if __name__ == "__main__":
    main()
