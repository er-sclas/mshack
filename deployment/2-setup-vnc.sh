#!/bin/bash
# ============================================================================
# VNC Server Setup Script
# Sets up TigerVNC with XFCE desktop for remote access
# ============================================================================

set -e

echo "=========================================="
echo "Setting up VNC Server"
echo "=========================================="

# Create VNC directory
mkdir -p ~/.vnc

# Create VNC startup script
echo "[1/4] Creating VNC startup script..."
cat > ~/.vnc/xstartup << 'EOF'
#!/bin/bash
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
exec startxfce4
EOF

chmod +x ~/.vnc/xstartup

# Create VNC config
echo "[2/4] Creating VNC configuration..."
cat > ~/.vnc/config << 'EOF'
geometry=1920x1080
depth=24
EOF

# Set VNC password
echo "[3/4] Setting VNC password..."
echo "Enter a password for VNC access (min 6 characters):"
vncpasswd

# Create systemd service for VNC
echo "[4/4] Creating systemd service..."
sudo tee /etc/systemd/system/vncserver@.service > /dev/null << EOF
[Unit]
Description=TigerVNC server on display %i
After=syslog.target network.target

[Service]
Type=forking
User=$USER
Group=$USER
WorkingDirectory=$HOME

ExecStartPre=/bin/sh -c '/usr/bin/vncserver -kill :%i > /dev/null 2>&1 || :'
ExecStart=/usr/bin/vncserver :%i -geometry 1920x1080 -depth 24
ExecStop=/usr/bin/vncserver -kill :%i

[Install]
WantedBy=multi-user.target
EOF

# Enable and start VNC service on display :1
sudo systemctl daemon-reload
sudo systemctl enable vncserver@1
sudo systemctl start vncserver@1

echo ""
echo "=========================================="
echo "VNC Server Setup Complete!"
echo "=========================================="
echo ""
echo "VNC is running on display :1 (port 5901)"
echo ""
echo "To connect:"
echo "  1. Open your VNC client (RealVNC, TigerVNC Viewer, etc.)"
echo "  2. Connect to: YOUR_VM_IP:5901"
echo "  3. Enter the password you just set"
echo ""
echo "IMPORTANT: Open firewall port 5901:"
echo "  GCP:   gcloud compute firewall-rules create allow-vnc --allow tcp:5901"
echo "  AWS:   Add inbound rule for TCP 5901 in Security Group"
echo "  Azure: Add inbound port rule for 5901"
echo ""
