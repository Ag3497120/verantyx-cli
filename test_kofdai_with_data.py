#!/usr/bin/env python3
"""
Kofdai型全同調エンジンの実運用テスト（学習データあり）
"""

from pathlib import Path
from verantyx_cli.engine.standalone_ai import VerantyxStandaloneAI
from verantyx_cli.engine.knowledge_learner import KnowledgeLearner
import json

def setup_test_data():
    """テストデータを設定"""
    cross_file = Path.home() / '.verantyx' / 'cross_memory.jcross'

    # KnowledgeLearnerでテストデータを追加
    learner = KnowledgeLearner(cross_file)

    # テストQ&Aを追加
    test_qa = [
        {
            "question": "openaiとは",
            "answer": "OpenAIは人工知能の研究と開発を行う米国の企業です。GPT-4などの大規模言語モデルを開発しています。",
            "entity": "openai",
            "intent": "definition"
        },
        {
            "question": "rustとは",
            "answer": "Rustはメモリ安全性とパフォーマンスを重視したシステムプログラミング言語です。",
            "entity": "rust",
            "intent": "definition"
        },
        {
            "question": "pythonとは",
            "answer": "Pythonは読みやすく書きやすい高水準プログラミング言語で、AI・機械学習・Webアプリ開発など幅広く使われています。",
            "entity": "python",
            "intent": "definition"
        }
    ]

    print("📚 Setting up test data...")
    for qa in test_qa:
        learner.add_qa_pattern(
            question=qa["question"],
            answer=qa["answer"],
            confidence=1.0,
            qa_type="definition"
        )
    print(f"✅ Added {len(test_qa)} Q&A patterns\n")


def test_kofdai_with_data():
    """学習データありでKofdai型エンジンをテスト"""

    # テストデータ設定
    setup_test_data()

    # スタンドアロンAI初期化
    cross_file = Path.home() / '.verantyx' / 'cross_memory.jcross'
    ai = VerantyxStandaloneAI(cross_file, enable_skills=False)

    print("=" * 70)
    print("🌊 Kofdai型全同調エンジン - 実運用テスト（学習データあり）")
    print("=" * 70)
    print("")

    # テスト入力（異なる表現）
    test_cases = [
        {
            "inputs": ["openaiとは", "openai", "openaiって何"],
            "expected_pattern": "definition_query"
        },
        {
            "inputs": ["それについて教えて"],
            "expected_pattern": "pronoun_reference"
        },
        {
            "inputs": ["ありがとう"],
            "expected_pattern": "gratitude"
        }
    ]

    for test_case in test_cases:
        print(f"Test Group: {test_case['expected_pattern']}")
        print("-" * 70)

        for text in test_case["inputs"]:
            print(f"\n📥 Input: {text}")

            # Kofdai型処理
            response = ai.generate_response(text)

            # 応答の一部を表示（長すぎるので最初の300文字のみ）
            if len(response) > 300:
                print(response[:300] + "...\n")
            else:
                print(response + "\n")

        print("=" * 70)
        print("")

    # Cross空間状態表示
    print("\n" + ai.kofdai_engine.get_space_visualization())


if __name__ == "__main__":
    test_kofdai_with_data()
