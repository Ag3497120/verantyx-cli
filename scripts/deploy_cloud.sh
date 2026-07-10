#!/bin/bash
set -e

# Compress the source code excluding heavy binaries and node_modules
tar -czvf verantyx-cloud.tar.gz \
    --exclude="node_modules" \
    --exclude="target" \
    --exclude="*.jgen" \
    --exclude=".git" \
    --exclude="predictions_verified.jsonl" \
    .

echo "==========================================="
echo " Archive created: verantyx-cloud.tar.gz"
echo " "
echo " Upload to your cloud instance using:"
echo " scp -i ~/.ssh/your_key.pem verantyx-cloud.tar.gz root@<CLOUD_IP>:~/"
echo "==========================================="
