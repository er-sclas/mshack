#!/bin/bash
# Deploy the application
set -e

APP_DIR="$HOME/chepauk-traffic"

echo "=========================================="
echo "Deploying Application"
echo "=========================================="

cd "$APP_DIR"

# Setup Python venv
echo "[1/5] Setting up Python environment..."
cd backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install fastapi uvicorn python-dotenv google-cloud-firestore numpy pandas pydantic

# Setup frontend
echo "[2/5] Setting up frontend..."
cd ../frontend
npm install
npm run build

# Configure nginx
echo "[3/5] Configuring nginx..."
sudo tee /etc/nginx/sites-available/chepauk > /dev/null << 'NGINX'
server {
    listen 80;
    server_name _;

    location / {
        root /home/ubuntu/chepauk-traffic/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    location ~ ^/(run-simulation|runs|edges|network|predict|compare|health) {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
NGINX

sudo ln -sf /etc/nginx/sites-available/chepauk /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# Create backend service
echo "[4/5] Creating backend service..."
sudo tee /etc/systemd/system/chepauk-backend.service > /dev/null << EOF
[Unit]
Description=Chepauk Traffic Backend
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR/backend
Environment="PATH=$APP_DIR/backend/venv/bin"
ExecStart=$APP_DIR/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable chepauk-backend
sudo systemctl start chepauk-backend

echo "[5/5] Opening firewall port 8000..."
sudo ufw allow 8000/tcp 2>/dev/null || true

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Web app: http://$(curl -s ifconfig.me)"
echo ""
echo "To run SUMO-GUI, use the browser SSH with:"
echo "  cd ~/chepauk-traffic/simulation && sumo-gui -c chepauk.sumocfg"
