import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from verantyx.cross_engine.jcross_extraction_parser import JCrossExtractionParser

def run_tests():
    bad_llm_output = """
Here are the extracted fragments based on your request:

* ■ JCROSS_FRAG_95_1
  【源泉】: idx_95
  【主体】 Admon
  - 【関係】 Assigned_Shift
  【客体】: 8 am - 4 pm  
  【文脈】: Sunday_Shift_Rotation
  【状態】   確定
  【軌道】 [遡: idx_95]

And another one that is clustered together:
■ JCROSS_FRAG_999_2
【源泉】idx_999【主体】Unknown Person 【関係】Works 【客体】Unknown 【文脈】Shift 【状態】欠落 【軌道】[遡: idx_999]

Hope this helps!
"""
    fragments = JCrossExtractionParser.parse(bad_llm_output)
    print("Parsed Fragments:")
    for i, f in enumerate(fragments):
        print(f"[{i}]: {f}")

    assert len(fragments) == 2, f"Expected 2 fragments, got {len(fragments)}"
    
    assert fragments[0]["__id__"] == "JCROSS_FRAG_95_1"
    assert fragments[0]["subject"] == "Admon"
    assert fragments[0]["predicate"] == "Assigned_Shift"
    assert fragments[0]["object"] == "8 am - 4 pm"
    
    assert fragments[1]["__id__"] == "JCROSS_FRAG_999_2"
    assert fragments[1]["subject"] == "Unknown Person"
    assert fragments[1]["state"] == "欠落"
    assert fragments[1]["trace"] == "idx_999"
    
    print("\nAll tests passed successfully for Fuzzy Parsing!")

if __name__ == "__main__":
    run_tests()
