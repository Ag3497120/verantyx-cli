#!/usr/bin/env python3
"""
Learn from Camera
カメラからオブジェクトを学習

MacBookのカメラでリアルタイムに物を見せながら学習する。

使い方:
    python -m verantyx_cli.vision.learn_from_camera

操作:
    [スペース] キャプチャ＆学習
    [r] 認識モード切り替え
    [l] 学習済みオブジェクト一覧
    [q] 終了
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional
import argparse

try:
    import cv2
    import numpy as np
    from PIL import Image
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from verantyx_cli.vision.object_cross_database import ObjectCrossDatabase
from verantyx_cli.vision.multi_layer_cross import MultiLayerCrossConverter


class CameraLearningSession:
    """カメラ学習セッション"""

    def __init__(self, camera_index: int = 0, db_path: Optional[Path] = None):
        """
        Initialize session

        Args:
            camera_index: カメラインデックス
            db_path: データベースパス
        """
        if not CV2_AVAILABLE:
            raise ImportError(
                "OpenCV is required. Install with: pip install opencv-python"
            )

        self.camera_index = camera_index
        self.db = ObjectCrossDatabase(db_path=db_path)
        # 軽量化: standardを使用（高速化のため）
        self.converter = MultiLayerCrossConverter(quality="standard")
        self.mode = "learning"  # "learning" or "recognition"
        self.cap = None
        self.frame_count = 0  # フレームカウンタ

    def run(self):
        """セッションを実行"""
        print()
        print("=" * 70)
        print("🎥 Verantyx Vision - Camera Learning")
        print("=" * 70)
        print()
        print("操作:")
        print("  [スペース] キャプチャ＆学習")
        print("  [r] 認識モード切り替え")
        print("  [l] 学習済みオブジェクト一覧")
        print("  [q] 終了")
        print()
        print("=" * 70)
        print()

        # データベースサマリー
        self.db.print_summary()

        # カメラ起動
        print("📷 カメラを起動中...")
        self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            print("❌ カメラを開けませんでした")
            return 1

        # 解像度設定
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        print("✅ カメラ起動完了")
        print()
        print(f"モード: {self.mode}")
        print()

        try:
            while True:
                # フレーム読み取り
                ret, frame = self.cap.read()

                if not ret:
                    print("❌ フレーム読み取りエラー")
                    break

                # フレームカウント
                self.frame_count += 1

                # モードに応じて処理
                display_frame = frame.copy()

                # 認識モードは10フレームに1回だけ実行（軽量化）
                if self.mode == "recognition" and self.frame_count % 10 == 0:
                    self._recognition_mode(display_frame)

                # ステータス表示
                self._draw_status(display_frame)

                # プレビュー表示
                cv2.imshow("Verantyx Vision - Camera Learning", display_frame)

                # キー入力
                key = cv2.waitKey(1) & 0xFF

                if key == ord('q'):
                    print("\n終了します...")
                    break
                elif key == ord(' '):
                    self._capture_and_learn(frame)
                elif key == ord('r'):
                    self._toggle_mode()
                elif key == ord('l'):
                    self._show_object_list()

        finally:
            if self.cap:
                self.cap.release()
            cv2.destroyAllWindows()

        print("\n✅ セッション終了")
        return 0

    def _capture_and_learn(self, frame):
        """キャプチャして学習"""
        print("\n" + "=" * 70)
        print("📸 キャプチャしました！")
        print("=" * 70)

        # 画像を一時保存
        temp_path = Path("/tmp/verantyx_capture.jpg")
        cv2.imwrite(str(temp_path), frame)

        # Cross構造に変換（軽量版）
        print("\nCross構造に変換中（標準品質）...")
        print("（この処理には数秒かかります）")

        try:
            cross_structure = self.converter.convert(temp_path)
            print("✅ Cross構造変換完了")
        except Exception as e:
            print(f"❌ 変換エラー: {e}")
            import traceback
            traceback.print_exc()
            return

        # ラベル入力
        print()
        object_name = input("これは何ですか？ > ").strip()

        if not object_name:
            print("❌ キャンセルしました")
            return

        # データベースに追加
        self.db.add_object(object_name, cross_structure)

        print()
        print("=" * 70)
        print()

    def _recognition_mode(self, frame):
        """認識モードで処理"""
        # 低解像度でCross変換（高速）
        temp_path = Path("/tmp/verantyx_recognition.jpg")
        cv2.imwrite(str(temp_path), frame)

        try:
            # 簡易版のCross構造（高速化のため）
            img = Image.open(temp_path)
            img = img.resize((64, 64))  # 小さくして高速化

            # 簡易Cross構造
            img_array = np.array(img)
            gray = np.mean(img_array, axis=2)

            cross_structure = {
                "axes": {
                    "UP": {"mean": float(np.mean(gray[:32, :]) / 255.0)},
                    "DOWN": {"mean": float(np.mean(gray[32:, :]) / 255.0)},
                    "RIGHT": {"mean": float(np.mean(gray[:, 32:]) / 255.0)},
                    "LEFT": {"mean": float(np.mean(gray[:, :32]) / 255.0)},
                    "FRONT": {"mean": float(np.mean(gray) / 255.0)},
                    "BACK": {"mean": 1.0 - float(np.mean(gray) / 255.0)}
                }
            }

            # 認識
            results = self.db.recognize(cross_structure, top_k=3, min_confidence=0.5)

            # 結果を画面に表示
            if results:
                best_match = results[0]
                text = f"{best_match['object']}: {best_match['confidence']:.1f}%"

                # 背景矩形
                cv2.rectangle(frame, (5, 5), (400, 80), (0, 0, 0), -1)

                # テキスト
                cv2.putText(
                    frame, text, (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                    (0, 255, 0), 2
                )

                # 類似オブジェクト
                if len(results) > 1:
                    similar_text = f"類似: {results[1]['object']} ({results[1]['confidence']:.0f}%)"
                    cv2.putText(
                        frame, similar_text, (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (200, 200, 200), 1
                    )

        except Exception as e:
            # エラーは無視（認識失敗）
            pass

    def _draw_status(self, frame):
        """ステータスを描画"""
        # ステータスバー背景
        height = frame.shape[0]
        cv2.rectangle(frame, (0, height - 60), (640, height), (0, 0, 0), -1)

        # モード表示
        mode_text = f"Mode: {self.mode.upper()}"
        cv2.putText(
            frame, mode_text, (10, height - 35),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6,
            (255, 255, 255), 1
        )

        # オブジェクト数
        obj_count = len(self.db.objects)
        count_text = f"Objects: {obj_count}"
        cv2.putText(
            frame, count_text, (10, height - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6,
            (255, 255, 255), 1
        )

        # 操作説明
        help_text = "[Space] Capture  [R] Recognize  [L] List  [Q] Quit"
        cv2.putText(
            frame, help_text, (200, height - 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5,
            (200, 200, 200), 1
        )

    def _toggle_mode(self):
        """モードを切り替え"""
        if self.mode == "learning":
            self.mode = "recognition"
            print("\n🔍 認識モードに切り替えました")
        else:
            self.mode = "learning"
            print("\n📚 学習モードに切り替えました")

    def _show_object_list(self):
        """学習済みオブジェクト一覧を表示"""
        print("\n" + "=" * 70)
        print("学習済みオブジェクト一覧")
        print("=" * 70)

        objects = self.db.list_objects()

        if not objects:
            print("（まだオブジェクトが学習されていません）")
        else:
            for obj in objects:
                print(f"  - {obj['name']}: {obj['sample_count']} サンプル")

        print("=" * 70)
        print()


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="Camera Learning - カメラからオブジェクトを学習"
    )

    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="カメラインデックス（デフォルト: 0）"
    )

    parser.add_argument(
        "--db-path",
        type=str,
        help="データベースパス（デフォルト: ~/.verantyx/object_database.json）"
    )

    args = parser.parse_args()

    # データベースパス
    db_path = None
    if args.db_path:
        db_path = Path(args.db_path).expanduser().absolute()

    # セッション実行
    session = CameraLearningSession(
        camera_index=args.camera,
        db_path=db_path
    )

    return session.run()


if __name__ == "__main__":
    sys.exit(main())
