import os
import json
import time
import hashlib

class ChronoRegistry:
    """
    The Mediator (仲介役)
    Maps spatial vectors (Eternal Memory indices) to actual code strings.
    Maintains the Git-like history of how code evolved in the vector space.
    """
    def __init__(self, workspace_dir, registry_file=".verantyx_chrono/registry.json"):
        self.workspace_dir = workspace_dir
        self.registry_file = os.path.join(workspace_dir, registry_file)
        self.registry_dir = os.path.dirname(self.registry_file)
        self.entries = {} # vector_index -> Metadata
        self.load()

    def load(self):
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    self.entries = json.load(f)
            except Exception as e:
                print(f"  [ChronoRegistry] Error loading registry: {e}")
                self.entries = {}
        else:
            os.makedirs(self.registry_dir, exist_ok=True)
            self.entries = {}

    def save(self):
        try:
            os.makedirs(self.registry_dir, exist_ok=True)
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(self.entries, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"  [ChronoRegistry] Error saving registry: {e}")

    def add_entry(self, vector_index: int, filepath: str, start_line: int, end_line: int, git_commit_hash: str, parent_index: int = -1, defer_save: bool = False):
        """
        Records a new state of code in the chronological vector space.
        Uses Git commit hash to link the spatial vector with the precise code state in Git.
        """
        entry = {
            "vector_index": vector_index,
            "filepath": filepath,
            "start_line": start_line,
            "end_line": end_line,
            "git_commit_hash": git_commit_hash,
            "timestamp": time.time(),
            "transition_from": parent_index
        }
        
        self.entries[str(vector_index)] = entry
        if not defer_save:
            self.save()
        return entry

    def get_entry(self, vector_index: int):
        return self.entries.get(str(vector_index))
        
    def find_latest_for_file(self, filepath: str):
        """
        Finds the most recent vector index representing a file's state.
        """
        latest_idx = -1
        latest_time = 0
        for idx_str, entry in self.entries.items():
            if entry["filepath"] == filepath:
                if entry["timestamp"] > latest_time:
                    latest_time = entry["timestamp"]
                    latest_idx = int(idx_str)
        return latest_idx if latest_idx != -1 else None

