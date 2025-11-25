#!/bin/bash
# ============================================================================
# SUMO Traffic Simulation - VM Setup Script
# Run this script on a fresh Ubuntu 22.04 VM (GCP, AWS, or Azure)
# ============================================================================

set -e  # Exit on error

echo "=========================================="
echo "Setting up SUMO Traffic Simulation VM"
echo "=========================================="

# Update system
echo "[1/8] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install desktop environment (XFCE - lightweight)
echo "[2/8] Installing XFCE desktop environment..."
sudo apt install -y xfce4 xfce4-goodies dbus-x11

# Install VNC server
echo "[3/8] Installing TigerVNC server..."
sudo apt install -y tigervnc-standalone-server tigervnc-common

# Install SUMO
echo "[4/8] Installing SUMO traffic simulator..."
sudo add-apt-repository -y ppa:sumo/stable
sudo apt update
sudo apt install -y sumo sumo-tools sumo-gui

# Install Python and dependencies
echo "[5/8] Installing Python and dependencies..."
sudo apt install -y python3 python3-pip python3-venv

# Install Node.js (for frontend)
echo "[6/8] Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install additional tools
echo "[7/8] Installing additional tools..."
sudo apt install -y git curl wget htop nginx

# Set SUMO_HOME environment variable
echo "[8/8] Setting environment variables..."
echo 'export SUMO_HOME="/usr/share/sumo"' >> ~/.bashrc
echo 'export PATH="$PATH:$SUMO_HOME/bin"' >> ~/.bashrc
source ~/.bashrc

echo ""
echo "=========================================="
echo "VM Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Run: ./2-setup-vnc.sh"
echo "  2. Run: ./3-deploy-app.sh"
echo ""
