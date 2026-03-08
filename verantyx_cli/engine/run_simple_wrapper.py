#!/usr/bin/env python3
"""
Simple Claude Wrapper - Cross Native with Simple Processors

VM変数ベースのシンプルなプロセッサでテスト
"""

import os
import sys
from pathlib import Path

# kofdai_computerのパスを追加
kofdai_dir = Path(__file__).parent.parent.parent.parent / "kofdai_computer"
sys.path.insert(0, str(kofdai_dir))

from kernel import KofdaiKernel
from jcross_parser import parse_jcross

# Simple IO変換器をインポート
sys.path.insert(0, str(Path(__file__).parent))
from processors_simple_io import get_simple_io_processors


def main():
    """Simple JCross wrapperを実行"""

    if len(sys.argv) < 3:
        print("Usage: run_simple_wrapper.py <host> <port> [project_path]")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    project_path = sys.argv[3] if len(sys.argv) > 3 else "."

    print("=" * 70)
    print("  Claude Wrapper - Simple Cross Native")
    print("=" * 70)
    print()
    print(f"🌐 Host: {host}")
    print(f"🔌 Port: {port}")
    print(f"📁 Project: {project_path}")
    print()

    # JCrossソースを読み込み
    jcross_file = Path(__file__).parent / "claude_wrapper_simple.jcross"

    if not jcross_file.exists():
        print(f"❌ JCross wrapper not found: {jcross_file}")
        sys.exit(1)

    with open(jcross_file, 'r', encoding='utf-8') as f:
        source = f.read()

    print(f"📜 Loading: {jcross_file.name}")
    print()

    # Cross Kernelを初期化
    kernel = KofdaiKernel()

    # Simple IO変換器を取得
    print("🔧 Loading Simple IO processors...")
    processors = get_simple_io_processors()
    print(f"✅ Loaded {len(processors)} processors")
    print("   Using VM variables for all I/O")
    print()

    # JCrossをパース
    print("⚙️  Parsing JCross program...")
    try:
        program = parse_jcross(source)
        print("✅ Parse complete")
        print()
    except Exception as e:
        print(f"❌ Parse error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # JCrossをCrossIRにコンパイル
    print("🔨 Compiling to CrossIR...")
    try:
        from jcross_ir_compiler import compile_jcross_to_ir
        compile_result = compile_jcross_to_ir(source)
        ir_program = compile_result.program
        print("✅ Compilation complete")
        print(f"   Instructions: {len(ir_program.instructions)}")
        print(f"   Labels: {len(ir_program.labels)}")
        print()
    except Exception as e:
        print(f"❌ Compilation error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # CrossIR VMで実行
    print("🎬 Executing Cross Native program...")
    print("=" * 70)
    print()

    try:
        from cross_ir_vm import CrossIRVM
        vm = CrossIRVM(ir_program, kernel, processors)

        # グローバル変数を設定
        vm.variables['socket_host'] = host
        vm.variables['socket_port'] = port
        vm.variables['project_path'] = project_path
        vm.variables['host'] = host
        vm.variables['port'] = port

        # 実行
        result = vm.run()

        print()
        print("=" * 70)
        print(f"✅ Program completed with result: {result}")

    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ Execution error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
