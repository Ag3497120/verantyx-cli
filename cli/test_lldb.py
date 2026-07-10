import lldb
import sys

debugger = lldb.SBDebugger.Create()
debugger.SetAsync(False)
target = debugger.CreateTarget("./.build/release/verantyx-cli")
error = lldb.SBError()
process = target.Launch(debugger.GetListener(), ["daemon", "qwen_27b.jcross"], None, None, "/dev/null", "/dev/null", "/dev/null", None, 0, False, error)
if not error.Success():
    print("Failed to launch:", error)
    sys.exit(1)

state = process.GetState()
print("State:", state)
thread = process.GetThreadAtIndex(0)
for frame in thread:
    print(frame)
