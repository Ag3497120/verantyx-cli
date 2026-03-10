#!/usr/bin/env python3
"""
継続的実行デーモン
30fps（または指定FPS）で連続実行
"""

import sys
import argparse
from pathlib import Path

# Import production daemon
from production_jcross_daemon import ProductionJCrossDaemon


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='本番JCross学習デーモン - 継続的実行モード')
    parser.add_argument('--fps', type=int, default=30, help='目標FPS（デフォルト: 30）')
    parser.add_argument('--duration', type=int, default=None, help='実行時間（秒）。指定しない場合は無限ループ')
    parser.add_argument('--gpu', action='store_true', help='GPUを使用')

    args = parser.parse_args()

    print("=" * 80)
    print("本番レベルJCross学習デーモン - 継続的実行")
    print("=" * 80)
    print()
    print(f"目標FPS: {args.fps}")
    print(f"実行時間: {'無限（Ctrl+Cで停止）' if args.duration is None else f'{args.duration}秒'}")
    print(f"GPU使用: {'あり' if args.gpu else 'なし'}")
    print()

    # デーモンを作成
    daemon = ProductionJCrossDaemon(
        use_gpu=args.gpu,
        log_dir=str(Path.home() / ".verantyx" / "production_logs")
    )

    print()

    # 継続的実行モード
    daemon.run_continuous_mode(
        target_fps=args.fps,
        duration_seconds=args.duration
    )

    print()
    print("=" * 80)
    print("実行完了")
    print("=" * 80)


if __name__ == "__main__":
    main()
