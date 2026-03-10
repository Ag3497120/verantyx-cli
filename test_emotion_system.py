#!/usr/bin/env python3
"""
Emotion Inference System Test
感情推測システムのテスト

システムが正しく動作するか検証。
"""

import sys
from pathlib import Path

# Add verantyx_cli to path
sys.path.insert(0, str(Path(__file__).parent))

from verantyx_cli.vision.experience_memory import ExperienceMemory
from verantyx_cli.vision.emotion_inference import EmotionInference


def test_experience_memory():
    """経験記憶のテスト"""
    print()
    print("=" * 70)
    print("Test 1: Experience Memory")
    print("=" * 70)
    print()

    # テスト用の記憶パス
    memory_path = Path("/tmp/test_emotion_memory.json")
    if memory_path.exists():
        memory_path.unlink()

    # 経験記憶を作成
    memory = ExperienceMemory(memory_path=memory_path)

    # テスト用のCross構造（単層）
    cross1 = {
        "axes": {
            "UP": {"mean": 0.5},
            "DOWN": {"mean": 0.5},
            "RIGHT": {"mean": 0.6},
            "LEFT": {"mean": 0.4},
            "FRONT": {"mean": 0.7},
            "BACK": {"mean": 0.3}
        }
    }

    cross2 = {
        "axes": {
            "UP": {"mean": 0.52},
            "DOWN": {"mean": 0.48},
            "RIGHT": {"mean": 0.62},
            "LEFT": {"mean": 0.38},
            "FRONT": {"mean": 0.72},
            "BACK": {"mean": 0.28}
        }
    }

    cross3 = {
        "axes": {
            "UP": {"mean": 0.8},
            "DOWN": {"mean": 0.2},
            "RIGHT": {"mean": 0.3},
            "LEFT": {"mean": 0.7},
            "FRONT": {"mean": 0.9},
            "BACK": {"mean": 0.1}
        }
    }

    # 観測
    print("📝 観測1を記録...")
    memory.observe(cross1)

    print("📝 観測2を記録...")
    memory.observe(cross2)

    print("📝 観測3を記録...")
    memory.observe(cross3)

    print()
    print(f"✅ 記憶された経験: {len(memory.timeline)}")
    print(f"✅ パターン数: {len(memory.patterns)}")

    # 類似度検索
    print()
    print("🔍 類似した経験を探索...")
    similar = memory.find_similar_moments(cross1, top_k=2)

    if similar:
        for i, match in enumerate(similar):
            print(f"   {i+1}. タイムスタンプ {match['timestamp']}: 類似度 {match['similarity']:.1%}")

    # 保存
    print()
    print("💾 記憶を保存...")
    memory.save()

    print()
    print("✅ Test 1 Passed!")
    print()

    # クリーンアップ
    if memory_path.exists():
        memory_path.unlink()


def test_emotion_inference():
    """感情推測のテスト"""
    print()
    print("=" * 70)
    print("Test 2: Emotion Inference")
    print("=" * 70)
    print()

    # テスト用の記憶パス
    memory_path = Path("/tmp/test_emotion_memory.json")
    if memory_path.exists():
        memory_path.unlink()

    # 経験記憶
    memory = ExperienceMemory(memory_path=memory_path)

    # 感情推測エンジン
    inference = EmotionInference(memory)

    # テスト用のCross構造
    cross1 = {
        "axes": {
            "UP": {"mean": 0.5},
            "DOWN": {"mean": 0.5},
            "RIGHT": {"mean": 0.6},
            "LEFT": {"mean": 0.4},
            "FRONT": {"mean": 0.7},
            "BACK": {"mean": 0.3}
        }
    }

    cross2 = {
        "axes": {
            "UP": {"mean": 0.52},
            "DOWN": {"mean": 0.48},
            "RIGHT": {"mean": 0.62},
            "LEFT": {"mean": 0.38},
            "FRONT": {"mean": 0.72},
            "BACK": {"mean": 0.28}
        }
    }

    cross3 = {
        "axes": {
            "UP": {"mean": 0.54},
            "DOWN": {"mean": 0.46},
            "RIGHT": {"mean": 0.64},
            "LEFT": {"mean": 0.36},
            "FRONT": {"mean": 0.74},
            "BACK": {"mean": 0.26}
        }
    }

    # 最初の観測（新鮮さ）
    print("👁️  観測1...")
    memory.observe(cross1)
    emotion1 = inference.infer(cross1)

    print(f"   感情: {inference.express_emotion(emotion1)}")
    assert emotion1["type"] == "novelty", "最初の観測は新鮮さであるべき"
    print("   ✅ 新鮮さが形成された")

    # 2回目の観測（期待）
    print()
    print("👁️  観測2...")
    memory.observe(cross2)
    emotion2 = inference.infer(cross2)

    print(f"   感情: {inference.express_emotion(emotion2)}")
    assert emotion2["type"] in ["expectation", "nostalgia"], "2回目は期待か懐かしさであるべき"
    print("   ✅ 期待が形成された")

    # 3回目の観測（予測検証）
    print()
    print("👁️  観測3（予測検証）...")
    memory.observe(cross3)

    # 前回の予測を検証
    reward = inference.validate_prediction(cross3)
    print(f"   報酬: {reward['type']}")
    assert reward["type"] in ["satisfaction", "surprise"], "報酬は満足か驚きであるべき"
    print("   ✅ 予測が検証された")

    emotion3 = inference.infer(cross3)
    print(f"   感情: {inference.express_emotion(emotion3)}")

    # サマリー
    print()
    summary = inference.get_emotion_summary()
    print(f"感情履歴: {summary['total']} 回")
    print(f"感情タイプ:")
    for emotion_type, count in summary.get('type_counts', {}).items():
        print(f"   - {emotion_type}: {count} 回")

    print()
    print("✅ Test 2 Passed!")
    print()

    # クリーンアップ
    if memory_path.exists():
        memory_path.unlink()


def test_emotion_expression():
    """感情表現のテスト"""
    print()
    print("=" * 70)
    print("Test 3: Emotion Expression")
    print("=" * 70)
    print()

    # ダミーの記憶
    memory_path = Path("/tmp/test_emotion_memory.json")
    if memory_path.exists():
        memory_path.unlink()

    memory = ExperienceMemory(memory_path=memory_path)
    inference = EmotionInference(memory)

    # 各感情タイプをテスト
    emotions = [
        {
            "type": "novelty",
            "FRONT": 0.8,
            "UP": 0.7,
            "DOWN": 0.3,
            "confidence": 0.3
        },
        {
            "type": "expectation",
            "FRONT": 0.9,
            "UP": 0.3,
            "DOWN": 0.7,
            "confidence": 0.8
        },
        {
            "type": "satisfaction",
            "UP": 0.6,
            "DOWN": 0.8,
            "FRONT": 0.9,
            "confidence": 0.9
        },
        {
            "type": "surprise",
            "UP": 0.9,
            "DOWN": 0.2,
            "BACK": 0.7,
            "confidence": 0.5
        },
        {
            "type": "nostalgia",
            "BACK": 0.9,
            "DOWN": 0.7,
            "confidence": 0.8
        }
    ]

    for emotion in emotions:
        text = inference.express_emotion(emotion)
        print(f"   {emotion['type']:15} → {text}")

    print()
    print("✅ Test 3 Passed!")
    print()

    # クリーンアップ
    if memory_path.exists():
        memory_path.unlink()


def main():
    """メイン関数"""
    print()
    print("=" * 70)
    print("🧠 Emotion Inference System Test")
    print("=" * 70)

    try:
        test_experience_memory()
        test_emotion_inference()
        test_emotion_expression()

        print()
        print("=" * 70)
        print("✅ All Tests Passed!")
        print("=" * 70)
        print()

        return 0

    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ Test Failed: {e}")
        print("=" * 70)
        print()
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
