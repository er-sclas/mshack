#!/bin/bash
# ============================================================================
# Application Deployment Script
# Deploys the Chepauk Traffic Simulation application
# ============================================================================

set -e

APP_DIR="$HOME/chepauk-traffic"

echo "=========================================="
echo "Deploying Chepauk Traffic Simulation"
echo "=========================================="

# Clone or update repository (replace with your actual repo URL)
echo "[1/7] Setting up application directory..."
if [ -d "$APP_DIR" ]; then
    echo "Directory exists, pulling latest changes..."
    cd "$APP_DIR"
    git pull || echo "Not a git repo, skipping pull"
else
    echo "Creating application directory..."
    mkdir -p "$APP_DIR"
fi

# If deploying from local machine, copy files instead of git clone
# scp -r /path/to/local/project/* user@vm-ip:~/chepauk-traffic/

echo "[2/7] Setting up Python virtual environment..."
cd "$APP_DIR"
python3 -m venv backend/venv
source backend/venv/bin/activate

echo "[3/7] Installing Python dependencies..."
pip install --upgrade pip
pip install fastapi uvicorn python-dotenv google-cloud-firestore numpy pandas pydantic

echo "[4/7] Installing frontend dependencies..."
cd "$APP_DIR/frontend"
npm install

echo "[5/7] Building frontend for production..."
npm run build

echo "[6/7] Setting up Nginx reverse proxy..."
sudo tee /etc/nginx/sites-available/chepauk-traffic > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    # Frontend (built React app)
    location / {
        root /home/ubuntu/chepauk-traffic/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Backend API proxy
    location /api {
        rewrite ^/api(.*)$ $1 break;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;
    }

    # Direct backend access (for existing API calls)
    location ~ ^/(run-simulation|runs|edges|network|predict|compare|health) {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/chepauk-traffic /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

echo "[7/7] Creating systemd services..."

# Backend service
sudo tee /etc/systemd/system/chepauk-backend.service > /dev/null << EOF
[Unit]
Description=Chepauk Traffic Backend
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR/backend
Environment="PATH=$APP_DIR/backend/venv/bin"
Environment="DISPLAY=:1"
ExecStart=$APP_DIR/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable chepauk-backend
sudo systemctl start chepauk-backend

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Services running:"
echo "  - Frontend: http://YOUR_VM_IP (port 80)"
echo "  - Backend:  http://YOUR_VM_IP:8000"
echo "  - VNC:      YOUR_VM_IP:5901"
echo ""
echo "To check status:"
echo "  sudo systemctl status chepauk-backend"
echo "  sudo systemctl status nginx"
echo "  sudo systemctl status vncserver@1"
echo ""
echo "Logs:"
echo "  sudo journalctl -u chepauk-backend -f"
echo ""
