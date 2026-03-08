#!/usr/bin/env python3
"""
Shape Recognition JCross Runner
shape_recognition.jcross を実行して画像から形状を認識
"""

import sys
from pathlib import Path
from typing import Dict, Any
import numpy as np
from PIL import Image

# Cross IR関連をインポート
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "kofdai_computer"))

from jcross_compiler import compile_jcross_file
from verantyx_cli.engine.cross_ir_vm import CrossIRVM
from verantyx_cli.vision.vision_processors import create_vision_processors


def run_shape_recognition_on_image(image_path: Path) -> Dict[str, Any]:
    """
    画像に対して形状認識を実行

    Args:
        image_path: 画像ファイルパス

    Returns:
        認識結果 {"shape": str, "confidence": float, ...}
    """
    print(f"🔍 Shape Recognition: {image_path.name}")
    print("=" * 70)
    print()

    # 1. 画像を読み込み
    print("📖 画像を読み込み中...")
    try:
        image = Image.open(image_path).convert('RGB')
        print(f"   サイズ: {image.width}x{image.height}")
        print(f"   ✅ 読み込み完了")
        print()
    except Exception as e:
        print(f"   ❌ 画像読み込みエラー: {e}")
        return {"error": str(e)}

    # 2. JCrossプログラムをコンパイル
    jcross_path = Path(__file__).parent / "shape_recognition.jcross"
    print(f"⚙️  JCrossプログラムをコンパイル中: {jcross_path.name}")

    try:
        program_ir = compile_jcross_file(str(jcross_path))
        print(f"   ✅ コンパイル完了 ({len(program_ir.instructions)} 命令)")
        print()
    except Exception as e:
        print(f"   ❌ コンパイルエラー: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"Compile error: {e}"}

    # 3. 視覚認識プロセッサを作成
    print("🔧 視覚認識プロセッサを初期化中...")
    processors = create_vision_processors()
    print(f"   ✅ {len(processors)} 個のプロセッサを登録")
    print()

    # 4. Cross IR VMを起動
    print("🚀 Cross IR VMを起動中...")
    vm = CrossIRVM(program_ir, processors=processors)

    # 画像データをVMに渡す
    vm.variables["image_data"] = np.array(image)
    vm.variables["width"] = image.width
    vm.variables["height"] = image.height

    print("   ✅ VM起動完了")
    print()

    # 5. プログラムを実行
    print("▶️  JCrossプログラムを実行中...")
    print("-" * 70)
    print()

    try:
        result = vm.run()
        print()
        print("-" * 70)
        print("   ✅ 実行完了")
        print()
    except Exception as e:
        print()
        print("-" * 70)
        print(f"   ❌ 実行エラー: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"Runtime error: {e}"}

    # 6. 結果を取得
    print("📊 認識結果:")
    print()

    # VMの変数から結果を取得
    recognized_shape = vm.variables.get("recognized_shape", "unknown")
    confidence = vm.variables.get("confidence", 0.0)
    cross_pattern = vm.variables.get("cross_pattern", {})
    point_count = vm.variables.get("point_count", 0)

    result = {
        "shape": recognized_shape,
        "confidence": confidence,
        "cross_pattern": cross_pattern,
        "point_count": point_count
    }

    print(f"   形状: {recognized_shape}")
    print(f"   信頼度: {confidence:.2f}")
    print(f"   Cross点数: {point_count}")
    print()

    print("=" * 70)

    return result


def main():
    """メイン関数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Cross形状認識 - JCross Implementation"
    )
    parser.add_argument(
        "image",
        type=str,
        help="画像ファイルパス"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="結果を保存するJSONファイル（オプション）"
    )

    args = parser.parse_args()

    # 画像パスを確認
    image_path = Path(args.image).expanduser().absolute()

    if not image_path.exists():
        print(f"❌ 画像が見つかりません: {image_path}")
        return 1

    # 形状認識を実行
    result = run_shape_recognition_on_image(image_path)

    # エラーチェック
    if "error" in result:
        print(f"\n❌ エラーが発生しました: {result['error']}")
        return 1

    # 結果を保存
    if args.output:
        import json
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"\n💾 結果を保存しました: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
