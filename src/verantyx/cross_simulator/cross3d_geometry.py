from typing import Dict, List, Tuple
from ..jcross_lang.parser import JCrossNode

class Cross3DGeometryEngine:
    """
    3D Cross Geometry Engine for Verantyx.
    Maps logical JCross nodes into a mathematically verifiable 3D space,
    solving relationships via deterministic topologies rather than LLM guesswork.
    """
    
    def __init__(self):
        # Maps node_id -> (X, Y, Z) coordinates
        self.spatial_registry: Dict[str, Tuple[float, float, float]] = {}
        # Stores the original parsed AST
        self.knowledge_graph: Dict[str, JCrossNode] = {}
        
    def map_graph(self, nodes: List[JCrossNode]):
        """
        Takes parsed declarative nodes and assigns them an initial 3D coordinate
        based on their dimensional tags and semantic gravity.
        """
        for node in nodes:
            self.knowledge_graph[node.node_id] = node
            
            # X: Temporal/Causal axis (time sequence)
            # Y: Semantic abstraction axis (hierarchy)
            # Z: Gravity / Relevance Depth (0 = Front/Conscious, Negative = Subconscious)
            
            # Defaults
            x, y, z = 0.0, 0.0, 0.0
            
            if "時" in node.dimensions:
                x = node.dimensions["時"]
            if "空" in node.dimensions:
                y = node.dimensions["空"]
            if "重" in node.dimensions:
                # Gravity attracts towards Z=0 (Conscious forefront)
                z = -abs(node.dimensions["重"]) 
                
            self.spatial_registry[node.node_id] = (x, y, z)
            
    def query_nearest_neighbors(self, query_vector: Tuple[float, float, float], limit: int = 5) -> List[str]:
        """
        Finds nodes physically closest to the query coordinate in the Cross3D space.
        Distance d = sqrt(dx^2 + dy^2 + dz^2).
        """
        distances = []
        qx, qy, qz = query_vector
        for node_id, (nx, ny, nz) in self.spatial_registry.items():
            dist = ((nx - qx)**2 + (ny - qy)**2 + (nz - qz)**2) ** 0.5
            distances.append((dist, node_id))
            
        distances.sort(key=lambda item: item[0])
        return [node_id for _, node_id in distances[:limit]]
        
    def determine_collision(self, node_a: str, node_b: str, threshold: float = 0.1) -> bool:
        """
        Logical collision detection. If two concepts are forced into the same
        spatial region, the framework triggers a "Tension Resolution" event.
        """
        if node_a not in self.spatial_registry or node_b not in self.spatial_registry:
            return False
            
        ax, ay, az = self.spatial_registry[node_a]
        bx, by, bz = self.spatial_registry[node_b]
        
        dist = ((ax - bx)**2 + (ay - by)**2 + (az - bz)**2) ** 0.5
        return dist <= threshold
