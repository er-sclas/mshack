#!/bin/bash
# Full setup script for SUMO Traffic Simulation on GCP VM
set -e

echo "=========================================="
echo "SUMO Traffic Simulation - Full Setup"
echo "=========================================="

# Update system
echo "[1/6] Updating system..."
sudo apt update && sudo apt upgrade -y

# Install SUMO
echo "[2/6] Installing SUMO..."
sudo add-apt-repository -y ppa:sumo/stable
sudo apt update
sudo apt install -y sumo sumo-tools sumo-gui

# Install Python
echo "[3/6] Installing Python dependencies..."
sudo apt install -y python3 python3-pip python3-venv

# Install Node.js
echo "[4/6] Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install nginx
echo "[5/6] Installing nginx..."
sudo apt install -y nginx

# Set environment
echo "[6/6] Setting environment variables..."
echo 'export SUMO_HOME="/usr/share/sumo"' >> ~/.bashrc
echo 'export DISPLAY=:0' >> ~/.bashrc
source ~/.bashrc

echo ""
echo "=========================================="
echo "System setup complete!"
echo "=========================================="
echo ""
echo "Now run: ./deploy-app.sh"
