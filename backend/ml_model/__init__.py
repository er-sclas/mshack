"""
ML Model Package for Traffic Prediction

This package provides temporal models for predicting traffic conditions
based on recent historical data. The architecture is designed to be
easily swappable - you can replace the baseline model with more
sophisticated approaches (LSTM, GNN, Transformer) without changing
the API interface.
"""

from .model import TrafficPredictor

__all__ = ["TrafficPredictor"]
