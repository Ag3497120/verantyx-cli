import subprocess
import sys

cmd = [
    "./.build/arm64-apple-macosx/release/verantyx-cli",
    "daemon",
    "/Users/motonishikoudai/verantyx-cli/cli/qwen_27b.jcross",
    "-v",
    "--embed-path", "/Users/motonishikoudai/verantyx-cli/qwen-14b/model-00001-of-00015.safetensors",
    "--embed-offset", "1192",
    "--embed-size", "2542796800",
    "--lm-head-path", "/Users/motonishikoudai/verantyx-cli/qwen-14b/model-00008-of-00015.safetensors",
    "--lm-head-offset", "60000",
    "--lm-head-size", "2542796800",
    "--norm-path", "/Users/motonishikoudai/verantyx-cli/qwen-14b/model-00015-of-00015.safetensors",
    "--norm-offset", "445693544",
    "--norm-size", "10240"
]

process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

out, err = process.communicate()
print("STDOUT:")
print(out.decode('utf-8'))
print("STDERR:")
print(err.decode('utf-8'))
print("EXIT CODE:", process.returncode)
