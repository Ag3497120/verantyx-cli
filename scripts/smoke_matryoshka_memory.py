#!/usr/bin/env python3
"""スモーク: マトリョーシカ記憶の入れ子 pack/expand/rewrap。"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from matryoshka_cross import CrossNode, wrap
from matryoshka_memory import (
    MemoryDepthBudget,
    budget_from_env,
    build_nested_from_company,
    expand_for_budget,
    nest_status,
    pack_cross_to_graph,
    rewrap_for_budget,
    unpack_graph_to_cross,
)


def _leaf(q: str, ans: str, conf: float = 0.7) -> CrossNode:
    return CrossNode.leaf(
        q,
        dist=[(ans, 1.0)],
        concepts=[ans],
        propositions=[f"A: {ans}"],
        confidence=conf,
        source="smoke",
        meta={"truth_status": "unreviewed"},
    )


def test_pack_unpack_roundtrip():
    inner = [_leaf(f"sub {i}", f"ans{i}", 0.5 + i * 0.1) for i in range(3)]
    root = wrap(inner, question="parent Q", source="smoke")
    mg = pack_cross_to_graph(root, l3_text="Q: parent → A: root")
    assert mg is not None
    assert mg.meta.get("matryoshka") is True
    assert mg.meta.get("cross_tree")
    back = unpack_graph_to_cross(mg)
    assert back is not None
    assert len(back.children) == 3
    assert back.question == "parent Q"
    print("ok pack/unpack", back.scale, len(back.children))


def test_expand_outer_first():
    kids = [_leaf(f"deep {i}", f"d{i}" * 20, 0.6) for i in range(4)]
    mid = wrap(kids, question="mid layer", source="smoke")
    root = wrap([mid], question="outer anchor about why then therefore", source="smoke")
    shallow = MemoryDepthBudget(think_level=0, max_scale_open=0, token_budget=512)
    deep = MemoryDepthBudget(think_level=2, max_scale_open=3, token_budget=512)
    v0 = expand_for_budget(root, shallow)
    v2 = expand_for_budget(root, deep)
    assert len(v0.texts) >= 1
    assert len(v2.texts) > len(v0.texts), (len(v0.texts), len(v2.texts), v0.texts, v2.texts)
    assert v2.scale_opened >= v0.scale_opened
    print("ok expand", "shallow_n=", len(v0.texts), "deep_n=", len(v2.texts),
          "opened=", v2.scale_opened)


def test_rewrap_collapses():
    many = [_leaf(f"leaf {i}", f"payload-{i}-" + ("x" * 40), 0.4 + (i % 5) * 0.1)
            for i in range(12)]
    root = wrap(many, question="fat nest", source="smoke")
    tight = MemoryDepthBudget(think_level=1, max_scale_open=1, token_budget=80)
    compact = rewrap_for_budget(root, tight)
    assert compact is not None
    assert len(compact.children) <= 5
    assert compact.meta.get("rewrapped") is True
    print("ok rewrap", "children", len(root.children), "→", len(compact.children))


def test_build_nested_budget():
    many = [_leaf(f"c{i}", f"a{i}", 0.5) for i in range(10)]
    root = wrap(many, question="company cross", source="smoke")
    os.environ["VERANTYX_MEMORY_TOKEN_BUDGET"] = "64"
    nested = build_nested_from_company(
        root, question="q", answer="final",
        budget=MemoryDepthBudget(think_level=0, max_scale_open=0, token_budget=64))
    assert nested is not None
    assert nested.meta.get("answer_anchor") == "final"
    print("ok build_nested", nested.meta.get("rewrapped"), len(nested.children or []))


def test_nest_status_env():
    os.environ["VERANTYX_MATRYOSHKA_MEMORY"] = "1"
    os.environ["VERANTYX_MEMORY_THINK"] = "1"
    st = nest_status()
    assert st["enabled"] is True
    assert st["budget"]["think_level"] == 1
    assert st["budget"]["max_scale_open"] == 1
    b = budget_from_env()
    assert b.think_level == 1
    print("ok nest_status", st["enabled"], st["budget"])


def main():
    test_pack_unpack_roundtrip()
    test_expand_outer_first()
    test_rewrap_collapses()
    test_build_nested_budget()
    test_nest_status_env()
    print("ALL SMOKES PASSED")


if __name__ == "__main__":
    main()
