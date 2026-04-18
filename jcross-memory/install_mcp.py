#!/usr/bin/env python3
import os
import json
import shutil
from pathlib import Path

# The path to the Cargo.toml of the JCross server
CURRENT_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = CURRENT_DIR / "Cargo.toml"

def inject_mcp_config(config_path_str, name="jcross-memory"):
    config_path = Path(config_path_str).expanduser()
    if not config_path.parent.exists():
        os.makedirs(config_path.parent, exist_ok=True)
        
    config = {"mcpServers": {}}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    config = json.loads(content)
        except Exception as e:
            print(f"[ERROR] Failed to read {config_path}: {e}")
            return False

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"][name] = {
        "command": "/Users/motonishikoudai/verantyx-cli/jcross-memory/target/release/jcross-memory",
        "args": []
    }

    # Backup original just in case
    if config_path.exists():
        backup_path = config_path.with_suffix('.json.bak')
        shutil.copy2(config_path, backup_path)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print(f"[SUCCESS] Injected {name} into {config_path}")
    return True

if __name__ == "__main__":
    print(f"=== Universal MCP Installer for JCross Memory ===")
    print(f"Server Manifest: {MANIFEST_PATH}\n")
    
    # 1. Google Antigravity
    inject_mcp_config("~/.gemini/antigravity/mcp_config.json")
    
    # 2. Claude Desktop
    inject_mcp_config("~/.claude/claude_desktop_config.json")
    
    # 3. Cursor IDE
    inject_mcp_config("~/.cursor/mcp.json")
    
    print("\n[DONE] Installation Complete. Please restart your IDEs/Desktop Apps to detect the new MCP Server.")
