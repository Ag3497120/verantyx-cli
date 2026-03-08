# Claude Wrapper Display Fixes

## Problem Summary

When using `verantyx chat`, messages sent to Claude were not visible in the Claude terminal tab, and Claude's responses were not being displayed.

## Root Causes Identified

### Issue 1: Missing Bidirectional Communication
The JCross wrapper (`claude_wrapper_simple.jcross`) was only sending messages to Claude via PTY but not reading Claude's output.

**Original flow:**
1. Receive message from Verantyx ✅
2. Send to Claude via PTY ✅
3. Read Claude's response ❌ **MISSING**
4. Display response ❌ **MISSING**

### Issue 2: Dual Wrapper Launch
The tab launcher was creating two wrapper processes:
- One wrapper in the visible terminal tab
- Another wrapper in the background

This caused conflicts and resource waste.

### Issue 3: Architecture Confusion
Earlier attempts tried to launch Claude directly in the tab (separate from wrapper), which created disconnected processes:
- Wrapper's PTY-controlled Claude (hidden subprocess)
- Directly-launched Claude (visible in tab)
- Messages sent to PTY Claude, but user sees the other Claude

## Solutions Implemented

### Fix 1: Added PTY Output Reading to JCross Wrapper

**File: `verantyx_cli/engine/claude_wrapper_simple.jcross`**

Added code to read and display Claude's output after each message:

```jcross
# Claudeからの出力を読み取り (0.5秒待機)
実行する io.pty_read = {"size": 4096, "timeout": 0.5}
入れる claude_output
捨てる

# 出力があれば表示
取り出す claude_output
辞書から取り出す "data"
入れる output_data
捨てる

# (length check logic...)

# 出力を表示
"🤖 Claude: "
表示する
取り出す output_data
表示する
""
表示する
```

**Result:** Wrapper now displays Claude's responses in the terminal tab

### Fix 2: Removed Duplicate Wrapper Launch

**File: `verantyx_cli/engine/claude_tab_launcher.py`**

**Before:**
```python
# Launch wrapper in new tab
claude_cmd = self._get_claude_command()  # Returns wrapper command
# ... run in tab ...

# THEN launch wrapper again in background!
wrapper_success = self._launch_wrapper_background()  # ❌ Duplicate!
```

**After:**
```python
# Launch wrapper in new tab ONLY
print(f"✅ Wrapper launched in new tab")
# No background launch
return True
```

**Result:** Single wrapper instance manages everything

### Fix 3: Unified Architecture

**Current flow:**
```
Verantyx CLI
    ↓ (socket)
Wrapper (visible in tab)
    ├─ Receives messages from Verantyx
    ├─ Sends to Claude via PTY
    ├─ Reads Claude's response via PTY
    └─ Displays response in tab
    ↓ (PTY)
Claude Process (subprocess of wrapper)
```

**User sees:**
- Wrapper initialization messages
- Messages received from Verantyx
- "✅ Claudeに送信完了"
- "🤖 Claude: [response]"

## Files Modified

1. **verantyx_cli/engine/claude_wrapper_simple.jcross**
   - Added PTY output reading (`io.pty_read`)
   - Added response display logic
   - Added length checking to avoid empty output

2. **verantyx_cli/engine/claude_tab_launcher.py**
   - Removed duplicate wrapper launch
   - Simplified launch flow
   - Removed unused `_launch_wrapper_background()` code
   - Updated cleanup to only track Claude PID

3. **verantyx_cli/engine/processors_verantyx_io.py** (already done)
   - Enhanced `pty_read_bytes()` to support VM variables
   - Reads `claude_fd` from VM context

## Testing

### Test Procedure

1. Start Verantyx:
   ```bash
   verantyx chat
   ```

2. Send a test message:
   ```
   こんにちは
   ```

3. Check the Claude wrapper tab - should show:
   ```
   🔄 メッセージ転送開始
   ✅ Claudeに送信完了
   🤖 Claude: [Claude's response]
   ```

### Expected Behavior

- ✅ Wrapper visible in separate terminal tab
- ✅ Messages sent from Verantyx appear in wrapper tab
- ✅ Messages forwarded to Claude via PTY
- ✅ Claude's responses read from PTY
- ✅ Responses displayed in wrapper tab with "🤖 Claude:" prefix
- ✅ Single wrapper process (no duplicates)

## Architecture Benefits

1. **Visibility**: User can see entire communication flow in wrapper tab
2. **Debugging**: All I/O operations logged and displayed
3. **Simplicity**: Single wrapper process manages everything
4. **Separation**: Wrapper in one tab, Verantyx UI in another
5. **Pure JCross**: All logic in JCross, Python only for I/O

## Next Steps

If issues persist:

1. **Check PTY timeout**: If Claude takes >0.5s to respond, increase timeout in `io.pty_read`
2. **Check socket connection**: Verify port numbers match between Verantyx and wrapper
3. **Check Claude startup**: Ensure Claude successfully forks (check "✅ Claude起動" message)
4. **Check message format**: Ensure messages start with "INPUT:" prefix
