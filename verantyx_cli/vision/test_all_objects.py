#!/usr/bin/env python3
"""
Test All Learned Objects
学習済みオブジェクトの一括テスト

データベース内の全オブジェクトを順番にテストする。

使い方:
    python -m verantyx_cli.vision.test_all_objects
"""

import sys
from pathlib import Path
from typing import Optional
import argparse

try:
    import cv2
    import numpy as np
    from PIL import Image
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from verantyx_cli.vision.object_cross_database import ObjectCrossDatabase


class ObjectTestSession:
    """オブジェクトテストセッション"""

    def __init__(self, camera_index: int = 0, db_path: Optional[Path] = None):
        """Initialize session"""
        if not CV2_AVAILABLE:
            raise ImportError(
                "OpenCV is required. Install with: pip install opencv-python"
            )

        self.camera_index = camera_index
        self.db = ObjectCrossDatabase(db_path=db_path)
        self.cap = None
        self.test_results = {}  # object_name -> test results

    def run(self):
        """テストセッションを実行"""
        print()
        print("=" * 70)
        print("🧪 Verantyx Vision - Object Test Session")
        print("=" * 70)
        print()

        # データベース確認
        if not self.db.objects:
            print("❌ データベースが空です")
            print("   先にオブジェクトを学習してください:")
            print("   python -m verantyx_cli.vision.learn_from_camera")
            return 1

        # 学習済みオブジェクトを表示
        self.db.print_summary()

        objects_list = self.db.list_objects()
        print(f"テスト対象: {len(objects_list)} 個のオブジェクト")
        print()

        # テスト開始確認
        input("準備ができたらEnterキーを押してください... ")

        # カメラ起動
        print("\n📷 カメラを起動中...")
        self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            print("❌ カメラを開けませんでした")
            return 1

        # 解像度設定
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        print("✅ カメラ起動完了")
        print()

        # 各オブジェクトをテスト
        for i, obj_info in enumerate(objects_list):
            object_name = obj_info['name']
            sample_count = obj_info['sample_count']

            print("=" * 70)
            print(f"テスト {i+1}/{len(objects_list)}: {object_name}")
            print(f"学習サンプル数: {sample_count}")
            print("=" * 70)

            # オブジェクトをカメラに見せるよう指示
            print(f"\n📸 '{object_name}' をカメラに見せてください")
            print("   準備ができたら[スペース]キーを押してください")
            print("   スキップする場合は[S]キーを押してください")
            print()

            # テスト実行
            result = self._test_object(object_name)

            if result:
                self.test_results[object_name] = result
                print(f"\n✅ テスト完了: {object_name}")
                print(f"   認識率: {result['success_rate']:.1f}%")
                print(f"   平均信頼度: {result['avg_confidence']:.1f}%")
            else:
                print(f"\n⏭️  スキップ: {object_name}")

            print()

        # カメラ解放
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()

        # 結果サマリー
        print()
        self._print_test_summary()

        return 0

    def _test_object(self, object_name: str) -> Optional[dict]:
        """オブジェクトをテスト"""
        test_count = 0
        success_count = 0
        confidences = []
        skipped = False

        try:
            while True:
                # フレーム読み取り
                ret, frame = self.cap.read()

                if not ret:
                    print("❌ フレーム読み取りエラー")
                    break

                # カメラプレビュー表示
                display_frame = frame.copy()

                # 指示を表示
                height = display_frame.shape[0]
                cv2.rectangle(display_frame, (0, 0), (640, 100), (0, 0, 0), -1)
                cv2.putText(
                    display_frame, f"Test: {object_name}", (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                    (255, 255, 255), 2
                )
                cv2.putText(
                    display_frame, "[Space] Test  [S] Skip", (10, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (200, 200, 200), 1
                )

                cv2.imshow("Verantyx Vision - Object Test", display_frame)

                # キー入力
                key = cv2.waitKey(1) & 0xFF

                if key == ord(' '):
                    # テスト実行
                    print(f"   テスト中... ", end="", flush=True)
                    recognition_result = self._recognize_frame(frame)

                    test_count += 1

                    if recognition_result and len(recognition_result) > 0:
                        top_match = recognition_result[0]
                        recognized_name = top_match['object']
                        confidence = top_match['confidence']

                        # 正解かチェック
                        is_correct = recognized_name == object_name

                        if is_correct:
                            success_count += 1
                            print(f"✅ 正解: {recognized_name} ({confidence:.1f}%)")
                        else:
                            print(f"❌ 不正解: {recognized_name} ({confidence:.1f}%) (正解: {object_name})")

                        confidences.append(confidence)
                    else:
                        print(f"❌ 認識できませんでした")

                    # 3回テストしたら終了
                    if test_count >= 3:
                        break

                elif key == ord('s') or key == ord('S'):
                    skipped = True
                    break

        except KeyboardInterrupt:
            print("\n⚠️  テスト中断")
            skipped = True

        if skipped or test_count == 0:
            return None

        # 結果を計算
        success_rate = (success_count / test_count * 100) if test_count > 0 else 0
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        return {
            'test_count': test_count,
            'success_count': success_count,
            'success_rate': success_rate,
            'avg_confidence': avg_confidence,
            'confidences': confidences
        }

    def _recognize_frame(self, frame):
        """フレームを認識"""
        # 一時ファイルに保存
        temp_path = Path("/tmp/verantyx_test.jpg")
        cv2.imwrite(str(temp_path), frame)

        try:
            # 簡易Cross構造
            img = Image.open(temp_path)
            img = img.resize((64, 64))
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
            results = self.db.recognize(cross_structure, top_k=3, min_confidence=0.0)
            return results

        except Exception as e:
            print(f"\n認識エラー: {e}")
            return None

    def _print_test_summary(self):
        """テスト結果サマリーを表示"""
        print("=" * 70)
        print("📊 テスト結果サマリー")
        print("=" * 70)
        print()

        if not self.test_results:
            print("テスト結果がありません")
            return

        total_tests = 0
        total_success = 0
        all_confidences = []

        print(f"{'オブジェクト':<20} {'テスト回数':<12} {'成功率':<12} {'平均信頼度':<12}")
        print("-" * 70)

        for object_name, result in sorted(self.test_results.items()):
            test_count = result['test_count']
            success_count = result['success_count']
            success_rate = result['success_rate']
            avg_confidence = result['avg_confidence']

            # 評価マーク
            if success_rate >= 90:
                mark = "🟢"
            elif success_rate >= 60:
                mark = "🟡"
            else:
                mark = "🔴"

            print(f"{mark} {object_name:<18} {test_count:<12} {success_rate:>6.1f}% {avg_confidence:>10.1f}%")

            total_tests += test_count
            total_success += success_count
            all_confidences.extend(result['confidences'])

        print("-" * 70)

        # 総合統計
        overall_success_rate = (total_success / total_tests * 100) if total_tests > 0 else 0
        overall_avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0

        print(f"{'総合':<20} {total_tests:<12} {overall_success_rate:>6.1f}% {overall_avg_confidence:>10.1f}%")
        print()

        # 評価
        print("総合評価:")
        if overall_success_rate >= 90:
            print("  🟢 優秀 - 認識精度が非常に高いです")
        elif overall_success_rate >= 70:
            print("  🟡 良好 - 認識精度は十分です")
        elif overall_success_rate >= 50:
            print("  🟠 要改善 - サンプルを追加学習することをお勧めします")
        else:
            print("  🔴 不良 - 再学習が必要です")

        print()
        print("改善のヒント:")
        print("  - 認識率が低い場合: 同じオブジェクトを複数角度から学習")
        print("  - 信頼度が低い場合: 照明条件を変えて追加学習")
        print("  - 誤認識が多い場合: 似たオブジェクトを別々に学習")
        print()
        print("=" * 70)


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="Object Test - 学習済みオブジェクトのテスト"
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

    # テストセッション実行
    session = ObjectTestSession(
        camera_index=args.camera,
        db_path=db_path
    )

    return session.run()


if __name__ == "__main__":
    sys.exit(main())
