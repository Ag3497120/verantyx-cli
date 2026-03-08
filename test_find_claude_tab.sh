#!/bin/bash
# Test script to find Claude tab

echo "Testing Claude tab detection..."

osascript <<'EOF'
tell application "Terminal"
    log "=== All Terminal Tabs ==="
    repeat with aWindow in windows
        log "Window: " & (name of aWindow)
        repeat with aTab in tabs of aWindow
            set tabProcesses to processes of aTab
            log "  Tab processes: " & tabProcesses

            -- Check if claude is in the list
            repeat with aProcess in tabProcesses
                if aProcess contains "claude" then
                    log "  >>> FOUND CLAUDE TAB! <<<"
                end if
            end repeat
        end repeat
    end repeat
end tell
EOF

echo ""
echo "Check Console.app for log output"
echo "Or try manually:"
echo "  osascript -e 'tell application \"Terminal\" to get processes of first tab of first window'"
