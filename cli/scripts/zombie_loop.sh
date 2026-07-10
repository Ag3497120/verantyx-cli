#!/bin/bash

echo "🧟 Starting Zombie Training Loop for Gemma 12B..."
echo "This loop will automatically catch OOM crashes and restart the training."

while true; do
    echo "====================================="
    echo "🚀 Booting Gemma Trainer Process..."
    echo "====================================="
    
    python3 scripts/gemma_trainer.py
    
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ Training completed successfully without crashing!"
        break
    else
        echo "💥 Process killed (likely Memory Limit / OOM). Exit Code: $EXIT_CODE"
        echo "⏳ Restarting from latest checkpoint in 5 seconds to clear memory..."
        sleep 5
    fi
done
