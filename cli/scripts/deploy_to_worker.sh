#!/bin/bash

# ==============================================================================
# Verantyx Worker Deployment Script (Thunderbolt Cluster)
# ==============================================================================

WORKER_IP=$1
WORKER_USER=${2:-$USER}  # Defaults to current username if not specified

if [ -z "$WORKER_IP" ]; then
    echo -e "\033[31mError:\033[0m Worker IP address required."
    echo "Usage: ./deploy_to_worker.sh <WORKER_IP> [WORKER_USERNAME]"
    echo "Example: ./deploy_to_worker.sh 10.0.0.2"
    exit 1
fi

echo -e "\033[36m[System] Initializing Thunderbolt Deployment to $WORKER_USER@$WORKER_IP...\033[0m"

# Get absolute path of the workspace root (parent of cli/scripts)
WORKSPACE_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
TARGET_DIR="~/verantyx-cli-worker"

# Use rsync over SSH to transfer ONLY the necessary files
# This skips all the 200,000+ unnecessary files (.venv, .pt, .memory, .exe, etc.)
rsync -avz --progress -e "ssh -o StrictHostKeyChecking=no" \
    --include="telepathic_coder_lossless.jgen" \
    --include="cli/" \
    --include="cli/scripts/" \
    --include="cli/scripts/*.py" \
    --exclude="*" \
    "$WORKSPACE_ROOT/" "$WORKER_USER@$WORKER_IP:$TARGET_DIR/"

if [ $? -eq 0 ]; then
    echo -e "\n\033[32m[Success] Deployment complete!\033[0m"
    echo "To start the Worker Daemon on Mac 2, run the following commands on Mac 2:"
    echo -e "\033[93m  ssh $WORKER_USER@$WORKER_IP\033[0m"
    echo -e "\033[93m  cd $TARGET_DIR\033[0m"
    echo -e "\033[93m  python3 cli/scripts/telepathic_coder.py --cluster-mode worker\033[0m"
else
    echo -e "\n\033[31m[Error] Deployment failed. Please ensure Mac 2 is reachable via SSH over Thunderbolt.\033[0m"
fi
