#!/usr/bin/env python3
"""
Simple Camera Test
カメラ動作の簡易テスト

OpenCVのカメラが正しく動作するか確認する。
Cross変換なしの軽量版。

使い方:
    python -m verantyx_cli.vision.test_camera_simple
"""

import sys

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("❌ OpenCVがインストールされていません")
    print("インストール: pip install opencv-python")
    sys.exit(1)


def test_camera(camera_index: int = 0):
    """カメラの簡易テスト"""
    print()
    print("=" * 70)
    print("🎥 Verantyx Vision - Simple Camera Test")
    print("=" * 70)
    print()
    print("操作:")
    print("  [q] 終了")
    print()
    print("=" * 70)
    print()

    # カメラ起動
    print("📷 カメラを起動中...")
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print("❌ カメラを開けませんでした")
        print()
        print("トラブルシューティング:")
        print("  1. カメラが他のアプリで使用されていないか確認")
        print("  2. カメラのアクセス許可を確認")
        print("  3. 別のカメラインデックスを試す（--camera 1）")
        return 1

    # 解像度設定
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("✅ カメラ起動完了")
    print()

    frame_count = 0

    try:
        while True:
            # フレーム読み取り
            ret, frame = cap.read()

            if not ret:
                print("❌ フレーム読み取りエラー")
                break

            frame_count += 1

            # ステータスをフレームに描画
            height = frame.shape[0]

            # ステータスバー背景
            cv2.rectangle(frame, (0, height - 40), (640, height), (0, 0, 0), -1)

            # フレーム数
            frame_text = f"Frame: {frame_count}"
            cv2.putText(
                frame, frame_text, (10, height - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (255, 255, 255), 1
            )

            # 操作説明
            help_text = "[Q] Quit"
            cv2.putText(
                frame, help_text, (500, height - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (200, 200, 200), 1
            )

            # プレビュー表示
            cv2.imshow("Verantyx Vision - Camera Test", frame)

            # キー入力
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q') or key == ord('Q'):
                print(f"\n終了します... (総フレーム数: {frame_count})")
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()

    print("\n✅ テスト完了")
    return 0


def main():
    """メイン関数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Simple Camera Test - カメラ動作確認"
    )

    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="カメラインデックス（デフォルト: 0）"
    )

    args = parser.parse_args()

    return test_camera(camera_index=args.camera)


if __name__ == "__main__":
    sys.exit(main())
