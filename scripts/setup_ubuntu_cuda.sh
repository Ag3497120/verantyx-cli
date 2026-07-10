#!/bin/bash
set -e

echo "==========================================="
echo " Verantyx Cloud Deploy Setup (Ubuntu CUDA)"
echo "==========================================="

# 1. Update and install basic dependencies
sudo apt-get update
sudo apt-get install -y build-essential curl git wget unzip pkg-config libssl-dev

# 2. Install Node.js (v20) via NVM
if ! command -v nvm &> /dev/null
then
    echo "Installing NVM and Node.js..."
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm install 20
    nvm use 20
fi

# 3. Install Rust
if ! command -v cargo &> /dev/null
then
    echo "Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
fi

# 4. Install Node dependencies
echo "Installing Node.js dependencies..."
npm install

# 5. Build the JCross Engine with CUDA
echo "Building jcross_engine for CUDA..."
cd jcross_engine
cargo build --release --lib --no-default-features --features cuda
cd ..

# 6. Download the .jgen model from Hugging Face
echo "Downloading qwen_9b_full.jgen from Hugging Face..."
if ! command -v hf &> /dev/null
then
    pip install -U "huggingface_hub[cli]"
fi

# Ensure HF uses the token if it's a private repo, otherwise download directly
huggingface-cli download kofdai/qwen9b-jgen qwen_9b_full.jgen --local-dir .

echo "==========================================="
echo " Setup Complete! You are ready to run:"
echo " npx tsx run_swe_bench_verified.ts"
echo "==========================================="
