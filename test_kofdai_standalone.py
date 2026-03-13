#!/usr/bin/env python3
"""
Kofdai型全同調エンジンの実運用テスト
"""

from pathlib import Path
from verantyx_cli.engine.standalone_ai import VerantyxStandaloneAI

def test_kofdai_resonance():
    """Kofdai型全同調エンジンのテスト"""

    # スタンドアロンAI初期化
    cross_file = Path.home() / '.verantyx' / 'cross_memory.jcross'
    ai = VerantyxStandaloneAI(cross_file, enable_skills=False)

    print("=" * 60)
    print("🌊 Kofdai型全同調エンジン - 実運用テスト")
    print("=" * 60)
    print("")

    # テスト入力
    test_inputs = [
        "openaiとは",
        "それについて教えて",
        "ありがとう",
        "こんにちは"
    ]

    for text in test_inputs:
        print(f"Input: {text}")
        print("-" * 60)

        # Kofdai型処理
        response = ai.generate_response(text)
        print(response)
        print("")
        print("=" * 60)
        print("")

    # Cross空間状態表示
    print(ai.kofdai_engine.get_space_visualization())

if __name__ == "__main__":
    test_kofdai_resonance()
