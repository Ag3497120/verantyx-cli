from typing import List
from ..jcross_lang.parser import JCrossNode

class MoERouter:
    """
    Mixture of Experts Router for JCross.
    Evaluates the top-layer 3D topology and decides which specific symbolic solver 
    (e.g., Math Solver, Logic Puzzle Solver, Visual ARC Solver)
    should be invoked, completely bypassing LLM probability generation.
    """
    
    def __init__(self, geometry_engine):
        self.geometry = geometry_engine
        
    def route_subproblem(self, active_node_ids: List[str]) -> str:
        """
        Determines the solver based on the dimensions and abstraction levels of the actively recalled nodes.
        """
        # Calculate center of gravity (averaging dimensions)
        avg_abstraction = 0.0
        math_signals = 0.0
        
        for node_id in active_node_ids:
            node = self.geometry.knowledge_graph.get(node_id)
            if node:
                avg_abstraction += node.abstract_level
                if "確" in node.dimensions: # Certainty / Mathematical certainty
                    math_signals += node.dimensions["確"]
                    
        num_nodes = max(1, len(active_node_ids))
        avg_abstraction /= num_nodes
        
        if math_signals > 0.8:
            return "solver.modal_logic"
        elif avg_abstraction > 0.5:
            return "solver.symbolic_graph"
        else:
            return "solver.cross3d_geometry"
