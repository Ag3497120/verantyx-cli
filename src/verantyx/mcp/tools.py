from typing import List, Dict, Optional
from src.verantyx.cross_simulator.puzzle_inference import PuzzleInferenceEngine

class JCrossMCPTools:
    """
    Standardizes Pure CPU Puzzle Engines as LLM-callable functions.
    """
    def __init__(self, context_fragments: List[Dict]):
        # We initialize the engine with the provided topological facts (fragments)
        self.engine = PuzzleInferenceEngine(context_fragments)

    def query_jcross_memory(self, search_text: str) -> str:
        """
        Queries the deterministic JCross Spatial Engine for absolute facts.
        
        Args:
            search_text: The explicit keywords to search the memory graph (e.g. "Admon shift").
        Returns:
            The exact topological object extracted from memory, or a miss message.
        """
        print(f"  [MCP Tool Called] query_jcross_memory('{search_text}')")
        
        # solve() uses Multi-hop native topology!
        # Notice we are using search_text which can be re-phrased by the LLM
        answer = self.engine.solve(search_text)
        
        if answer:
            return f"[JCross Absolute Truth]: {answer}"
        return "[JCross Result]: No direct topological connection found for these exact words. Please rephrase."
