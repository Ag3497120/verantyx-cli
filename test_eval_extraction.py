import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from verantyx.cross_engine.jcross_extraction_parser import JCrossExtractionParser

# Let's mock a query output
print("Checking parser manually")
test_str = """--- Chunk [idx_0] ---
■ JCROSS_FRAG_29ab12cd
【状態】 確定
【主体】 Apple
【関係】 is a
【客体】 Fruit
"""

frags = JCrossExtractionParser.parse(test_str)
print(frags)
