#!/usr/bin/env python3
"""
Dynamic JCross Video Analysis Runner
動画のフレーム間変化をJCrossコードの動的変更として解析
"""

import sys
from pathlib import Path
from typing import Dict, Any

# Cross IR関連をインポート
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "kofdai_computer"))

from jcross_compiler import compile_jcross_file
from verantyx_cli.engine.cross_ir_vm import CrossIRVM
from verantyx_cli.vision.dynamic_jcross_processors import create_dynamic_jcross_processors


def run_dynamic_video_analysis(video_path: Path) -> Dict[str, Any]:
    """
    動画に対して動的JCross解析を実行

    Args:
        video_path: 動画ファイルパス

    Returns:
        解析結果
    """
    print()
    print("=" * 70)
    print("🎬 Dynamic JCross Video Analysis")
    print("=" * 70)
    print(f"Video: {video_path.name}")
    print("=" * 70)
    print()

    # 1. JCrossプログラムをコンパイル
    jcross_path = Path(__file__).parent / "dynamic_video_analysis.jcross"
    print(f"⚙️  JCrossプログラムをコンパイル中...")
    print(f"   {jcross_path.name}")
    print()

    try:
        program_ir = compile_jcross_file(str(jcross_path))
        print(f"   ✅ コンパイル完了 ({len(program_ir.instructions)} 命令)")
        print()
    except Exception as e:
        print(f"   ❌ コンパイルエラー: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"Compile error: {e}"}

    # 2. 動的JCrossプロセッサを作成
    print("🔧 動的JCrossプロセッサを初期化中...")
    processors = create_dynamic_jcross_processors()
    print(f"   ✅ {len(processors)} 個のプロセッサを登録")
    print()

    # 3. Cross IR VMを起動
    print("🚀 Cross IR VMを起動中...")
    vm = CrossIRVM(program_ir, processors=processors)

    # 動画パスをVMに渡す
    vm.variables["video_path"] = str(video_path)

    print("   ✅ VM起動完了")
    print()

    # 4. プログラムを実行
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

    # 5. 結果を取得
    frame_count = vm.variables.get("frame_count", 0)
    diff_count = vm.variables.get("diff_count", 0)
    total_added = vm.variables.get("total_added", 0)
    total_removed = vm.variables.get("total_removed", 0)
    total_color_changed = vm.variables.get("total_color_changed", 0)

    result = {
        "frame_count": frame_count,
        "diff_count": diff_count,
        "total_added": total_added,
        "total_removed": total_removed,
        "total_color_changed": total_color_changed
    }

    print()
    print("=" * 70)

    return result


def main():
    """メイン関数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Dynamic JCross Video Analysis - フレーム間変化をJCrossコードの動的変更として解析"
    )
    parser.add_argument(
        "video",
        type=str,
        help="動画ファイルパス"
    )

    args = parser.parse_args()

    # 動画パスを確認
    video_path = Path(args.video).expanduser().absolute()

    if not video_path.exists():
        print(f"❌ 動画が見つかりません: {video_path}")
        return 1

    # 動的JCross解析を実行
    result = run_dynamic_video_analysis(video_path)

    # エラーチェック
    if "error" in result:
        print(f"\n❌ エラーが発生しました: {result['error']}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
