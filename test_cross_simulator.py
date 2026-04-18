from verantyx.jcross_lang.lexer import JCrossLexer
from verantyx.jcross_lang.parser import JCrossParser
from verantyx.cross_simulator.cross3d_geometry import Cross3DGeometryEngine
from verantyx.cross_simulator.gravity_solver import GravitySolver

def test_simulator():
    sample_jcross = """
■ JCROSS_NODE_M_50000_SYNC
【空間座相】
[核:5.0] [重:10.0] [時:1.0] [空:-2.5]
【連帯】
tm_test_SOTA:基底:1.0
void_arc:進化:0.95

■ JCROSS_tm_test_SOTA
【空間座相】
[重:2.0] [時:3.0] [空:0.0]
    """
    
    print("--- 1. Lexing ---")
    lexer = JCrossLexer(sample_jcross)
    tokens = lexer.tokenize()
    print(f"Generated {len(tokens)} tokens.")
    
    print("\n--- 2. Parsing AST ---")
    parser = JCrossParser(tokens)
    nodes = parser.parse()
    for n in nodes:
        print(f"Node ID: {n.node_id}")
        print(f"  Dimensions: {n.dimensions}")
        print(f"  Edges: {len(n.edges)}")
        
    print("\n--- 3. 3D Cross Geometry Engine ---")
    engine = Cross3DGeometryEngine()
    engine.map_graph(nodes)
    for nid, coords in engine.spatial_registry.items():
        print(f"Spatial Coord [{nid}]: X:{coords[0]} Y:{coords[1]} Z:{coords[2]}")
        
    print("\n--- 4. Gravity Solver (Flashback) ---")
    solver = GravitySolver(engine)
    
    # Step simulation 10 times to sink
    for _ in range(10):
        solver.step_simulation(decay_rate=2.0)
    
    for nid, coords in engine.spatial_registry.items():
        print(f"After Decay [{nid}]: Z_Depth = {coords[2]:.2f}")
        
    print("\n--- 5. Triggering Flashback (The Spark of Analogy) ---")
    solver.trigger_flashback("M_50000_SYNC")
    for nid, coords in engine.spatial_registry.items():
        print(f"After Flashback [{nid}]: Z_Depth = {coords[2]:.2f}")
        
if __name__ == "__main__":
    test_simulator()
