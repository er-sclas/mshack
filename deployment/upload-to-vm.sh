#!/bin/bash
# ============================================================================
# Upload project to cloud VM
# Usage: ./upload-to-vm.sh <VM_IP> [username]
# ============================================================================

if [ -z "$1" ]; then
    echo "Usage: ./upload-to-vm.sh <VM_IP> [username]"
    echo "Example: ./upload-to-vm.sh 34.123.45.67 ubuntu"
    exit 1
fi

VM_IP=$1
USERNAME=${2:-ubuntu}
PROJECT_DIR="$(dirname "$(dirname "$(realpath "$0")")")"

echo "=========================================="
echo "Uploading project to $USERNAME@$VM_IP"
echo "=========================================="

# Create tarball of project (excluding unnecessary files)
echo "[1/3] Creating archive..."
cd "$PROJECT_DIR"
tar -czvf /tmp/chepauk-traffic.tar.gz \
    --exclude='node_modules' \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='*.pyc' \
    --exclude='.env' \
    backend frontend simulation deployment

# Upload to VM
echo "[2/3] Uploading to VM..."
scp /tmp/chepauk-traffic.tar.gz "$USERNAME@$VM_IP":~

# Extract on VM
echo "[3/3] Extracting on VM..."
ssh "$USERNAME@$VM_IP" << 'ENDSSH'
mkdir -p ~/chepauk-traffic
cd ~
tar -xzvf chepauk-traffic.tar.gz -C chepauk-traffic
chmod +x ~/chepauk-traffic/deployment/*.sh
echo ""
echo "Files uploaded to ~/chepauk-traffic"
echo "Run the setup scripts:"
echo "  cd ~/chepauk-traffic/deployment"
echo "  ./1-setup-vm.sh"
echo "  ./2-setup-vnc.sh"
echo "  ./3-deploy-app.sh"
ENDSSH

# Cleanup
rm /tmp/chepauk-traffic.tar.gz

echo ""
echo "=========================================="
echo "Upload Complete!"
echo "=========================================="
echo ""
echo "SSH into your VM and run the setup scripts:"
echo "  ssh $USERNAME@$VM_IP"
echo "  cd ~/chepauk-traffic/deployment"
echo "  ./1-setup-vm.sh"
