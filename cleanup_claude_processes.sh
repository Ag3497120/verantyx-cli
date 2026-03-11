#!/bin/bash
# Cleanup script for orphaned Claude processes

echo "🔍 Searching for Claude processes..."
echo ""

# Find all Claude processes
PIDS=$(pgrep -f "claude" | grep -v $$)

if [ -z "$PIDS" ]; then
    echo "✅ No Claude processes found"
    exit 0
fi

echo "Found Claude processes:"
ps aux | grep claude | grep -v grep | grep -v cleanup_claude_processes

echo ""
echo "PIDs to kill: $PIDS"
echo ""

read -p "Kill all these Claude processes? (y/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🛑 Killing Claude processes..."

    for PID in $PIDS; do
        echo "  Killing PID $PID..."
        kill -9 $PID 2>/dev/null
    done

    echo ""
    echo "✅ Cleanup complete!"

    # Verify
    REMAINING=$(pgrep -f "claude" | wc -l)
    if [ $REMAINING -eq 0 ]; then
        echo "✅ All Claude processes terminated"
    else:
        echo "⚠️  $REMAINING process(es) still running"
        echo "   You may need to manually kill them:"
        echo "   ps aux | grep claude"
    fi
else
    echo "❌ Cancelled"
fi
