from typing import Dict, List
import time

class GravitySolver:
    """
    Simulates the Z-Depth Gravity Mechanics described in the Verantyx notes.
    "Forgotton" nodes are not deleted, they simply slide into infinite negative Z-depth
    (The Subconscious Ocean). Flashback events pull them rapidly to Z=0.
    """
    
    def __init__(self, geometry_engine):
        self.geometry_engine = geometry_engine
        
    def step_simulation(self, decay_rate: float = 0.1):
        """
        Advances the simulation one tick. All nodes naturally sink unless stimulated.
        """
        for node_id, (x, y, z) in self.geometry_engine.spatial_registry.items():
            node = self.geometry_engine.knowledge_graph[node_id]
            base_mass = node.dimensions.get("重", 1.0)
            
            # Decay the Z value based on mass (heavy things sink slightly slower,
            # or we model it such that active things float to Z=0)
            # We assume active is Z=0, subconscious is highly negative Z.
            
            new_z = z - (decay_rate / base_mass)
            self.geometry_engine.spatial_registry[node_id] = (x, y, new_z)
            
    def trigger_flashback(self, entity_id: str):
        """
        An extreme trigger event. "反物質級の強力なクエリ（フラッシュバック）"
        Pulls a node instantly to the conscious layer (Z=0) from infinite depth.
        """
        if entity_id in self.geometry_engine.spatial_registry:
            x, y, _ = self.geometry_engine.spatial_registry[entity_id]
            # Flashback instantly sets Z to 0 (Active consciousness)
            self.geometry_engine.spatial_registry[entity_id] = (x, y, 0.0)
            
            # Recursively pull immediate connected nodes up slightly (Spreading Activation)
            node = self.geometry_engine.knowledge_graph[entity_id]
            for edge in node.edges:
                neighbor_id = edge.target_node
                if neighbor_id in self.geometry_engine.spatial_registry:
                    nx, ny, nz = self.geometry_engine.spatial_registry[neighbor_id]
                    # Bring allies closer to the surface
                    self.geometry_engine.spatial_registry[neighbor_id] = (nx, ny, min(0.0, nz + edge.weight))
