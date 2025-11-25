# Cloud Deployment Guide - Chepauk Traffic Simulation

This guide walks you through deploying the SUMO traffic simulation with VNC access on a cloud VM.

## Quick Start (Google Cloud)

### Step 1: Create VM

```bash
# Create a VM with Ubuntu 22.04 (4 vCPUs, 16GB RAM recommended)
gcloud compute instances create sumo-traffic-vm \
  --zone=us-central1-a \
  --machine-type=e2-standard-4 \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=50GB \
  --tags=http-server,vnc-server

# Open firewall ports
gcloud compute firewall-rules create allow-vnc \
  --allow tcp:5901 \
  --target-tags=vnc-server

gcloud compute firewall-rules create allow-http \
  --allow tcp:80,tcp:8000 \
  --target-tags=http-server
```

### Step 2: Connect to VM

```bash
gcloud compute ssh sumo-traffic-vm --zone=us-central1-a
```

### Step 3: Upload Project Files

From your local machine:
```bash
# Compress project
cd "/Users/raahil/we wonn"
tar -czvf chepauk-traffic.tar.gz backend frontend simulation deployment

# Upload to VM
gcloud compute scp chepauk-traffic.tar.gz sumo-traffic-vm:~ --zone=us-central1-a

# On the VM, extract
ssh into the VM, then:
tar -xzvf chepauk-traffic.tar.gz
mv backend frontend simulation ~/chepauk-traffic/
```

### Step 4: Run Setup Scripts

```bash
# Make scripts executable
chmod +x ~/deployment/*.sh

# Run in order
cd ~/deployment
./1-setup-vm.sh      # Install system packages
./2-setup-vnc.sh     # Set up VNC (you'll be asked for a password)
./3-deploy-app.sh    # Deploy the application
```

---

## Alternative: AWS EC2

### Create Instance

1. Go to EC2 Dashboard > Launch Instance
2. Choose **Ubuntu 22.04 LTS**
3. Instance type: **t3.xlarge** (4 vCPU, 16GB) or larger
4. Storage: 50GB
5. Security Group: Allow ports 22, 80, 5901, 8000

### Connect and Deploy

```bash
ssh -i your-key.pem ubuntu@your-ec2-ip
# Then follow steps 3-4 above
```

---

## Alternative: Azure VM

### Create VM via CLI

```bash
az vm create \
  --resource-group myResourceGroup \
  --name sumo-traffic-vm \
  --image Ubuntu2204 \
  --size Standard_D4s_v3 \
  --admin-username azureuser \
  --generate-ssh-keys

# Open ports
az vm open-port --port 80 --resource-group myResourceGroup --name sumo-traffic-vm
az vm open-port --port 5901 --resource-group myResourceGroup --name sumo-traffic-vm
az vm open-port --port 8000 --resource-group myResourceGroup --name sumo-traffic-vm
```

---

## Connecting to VNC

### Option A: Direct VNC Connection

1. Download a VNC client:
   - **Windows**: [RealVNC Viewer](https://www.realvnc.com/en/connect/download/viewer/)
   - **Mac**: Built-in Screen Sharing or [RealVNC](https://www.realvnc.com/en/connect/download/viewer/)
   - **Linux**: `sudo apt install tigervnc-viewer`

2. Connect to: `YOUR_VM_IP:5901`
3. Enter the VNC password you set during setup

### Option B: SSH Tunnel (More Secure)

```bash
# Create SSH tunnel
ssh -L 5901:localhost:5901 user@YOUR_VM_IP

# Then connect VNC client to: localhost:5901
```

---

## Using the Application

### Access Points

| Service | URL |
|---------|-----|
| Web Dashboard | http://YOUR_VM_IP |
| Backend API | http://YOUR_VM_IP:8000 |
| VNC Desktop | YOUR_VM_IP:5901 |

### Running a Simulation with GUI

1. Open VNC and connect to the VM desktop
2. Open a web browser in the VNC session (Firefox)
3. Go to `http://localhost`
4. Create a scenario with "Open SUMO Visualization" enabled
5. Click "Run Simulation"
6. SUMO-GUI will open in the VNC desktop showing the traffic simulation

### Running Headless (No GUI)

1. Access `http://YOUR_VM_IP` from any browser
2. Create a scenario with "Open SUMO Visualization" **disabled**
3. View results in the web dashboard charts

---

## Managing Services

```bash
# Check status
sudo systemctl status chepauk-backend
sudo systemctl status vncserver@1
sudo systemctl status nginx

# Restart services
sudo systemctl restart chepauk-backend
sudo systemctl restart vncserver@1

# View logs
sudo journalctl -u chepauk-backend -f
```

---

## Firestore Setup (Optional)

If using Firestore for data persistence:

1. Create a Firebase project at https://console.firebase.google.com
2. Enable Firestore Database
3. Generate a service account key (Project Settings > Service Accounts)
4. Upload the key to the VM:
   ```bash
   scp credentials.json user@VM_IP:~/chepauk-traffic/backend/
   ```
5. Set environment variable:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="$HOME/chepauk-traffic/backend/credentials.json"
   ```

---

## Troubleshooting

### VNC Not Connecting
```bash
# Check if VNC is running
sudo systemctl status vncserver@1

# Restart VNC
sudo systemctl restart vncserver@1

# Check firewall
sudo ufw status
sudo ufw allow 5901/tcp
```

### SUMO-GUI Not Opening
```bash
# Make sure DISPLAY is set
export DISPLAY=:1

# Test SUMO-GUI manually
sumo-gui
```

### Backend Not Starting
```bash
# Check logs
sudo journalctl -u chepauk-backend -n 50

# Check Python environment
source ~/chepauk-traffic/backend/venv/bin/activate
python -c "import fastapi; print('OK')"
```

---

## Cost Estimates

| Cloud | Instance Type | Monthly Cost (approx) |
|-------|---------------|----------------------|
| GCP | e2-standard-4 | $100-120 |
| AWS | t3.xlarge | $120-140 |
| Azure | Standard_D4s_v3 | $140-160 |

**Tip**: Use preemptible/spot instances for ~70% savings if you don't need 24/7 uptime.
