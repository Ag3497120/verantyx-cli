#!/usr/bin/env python3
"""
Learn from SSD Videos
SSD内の動画から学習

ユーザーが動画を選択して、好奇心駆動で学習。
"""

import sys
import cv2
from pathlib import Path
import numpy as np
from PIL import Image
import time
from typing import List, Optional

from verantyx_cli.engine.jcross_bootstrap import ZeroYearOldJCross
from verantyx_cli.vision.multi_layer_cross import MultiLayerCrossConverter


def find_videos(search_paths: List[Path]) -> List[Path]:
    """
    動画ファイルを探す

    Args:
        search_paths: 検索するパスのリスト

    Returns:
        見つかった動画ファイルのリスト
    """
    videos = []
    extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']

    for search_path in search_paths:
        if not search_path.exists():
            continue

        for ext in extensions:
            videos.extend(search_path.glob(f'*{ext}'))
            videos.extend(search_path.glob(f'**/*{ext}'))

    # 重複を除去してソート
    videos = sorted(list(set(videos)))

    return videos


def get_video_info(video_path: Path) -> Optional[dict]:
    """
    動画情報を取得

    Args:
        video_path: 動画ファイルのパス

    Returns:
        動画情報の辞書
    """
    try:
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            return None

        info = {
            'path': video_path,
            'frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            'fps': cap.get(cv2.CAP_PROP_FPS),
            'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'duration': int(cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)),
            'size': video_path.stat().st_size
        }

        cap.release()
        return info

    except Exception as e:
        return None


def format_size(size_bytes: int) -> str:
    """バイトサイズを人間が読みやすい形式に変換"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def select_video(videos: List[Path]) -> Optional[Path]:
    """
    動画を選択

    Args:
        videos: 動画ファイルのリスト

    Returns:
        選択された動画のパス
    """
    print()
    print("=" * 80)
    print("📹 SSD内の動画ファイル")
    print("=" * 80)
    print()

    if not videos:
        print("❌ 動画ファイルが見つかりませんでした")
        return None

    # 動画情報を取得
    print("動画情報を取得中...")
    video_infos = []
    for i, video in enumerate(videos[:20]):  # 最大20個
        print(f"  {i+1}/{min(20, len(videos))}...", end='\r')
        info = get_video_info(video)
        if info:
            video_infos.append(info)

    print()
    print()

    if not video_infos:
        print("❌ 読み込める動画がありませんでした")
        return None

    # リスト表示
    print(f"見つかった動画: {len(video_infos)}個")
    print()

    for i, info in enumerate(video_infos):
        print(f"[{i+1}] {info['path'].name}")
        print(f"    時間: {info['duration']}秒, " +
              f"フレーム: {info['frames']}, " +
              f"解像度: {info['width']}x{info['height']}, " +
              f"サイズ: {format_size(info['size'])}")
        print()

    # 選択
    while True:
        try:
            choice = input(f"動画を選択してください (1-{len(video_infos)}, 0=キャンセル): ").strip()

            if choice == '0':
                return None

            idx = int(choice) - 1
            if 0 <= idx < len(video_infos):
                return video_infos[idx]['path']
            else:
                print(f"❌ 1-{len(video_infos)}の範囲で選択してください")

        except ValueError:
            print("❌ 数字を入力してください")
        except KeyboardInterrupt:
            print()
            return None


def learn_from_video(video_path: Path, max_frames: int = 100, skip_frames: int = 5):
    """
    動画から学習

    Args:
        video_path: 動画ファイルのパス
        max_frames: 最大処理フレーム数
        skip_frames: スキップするフレーム数
    """
    print()
    print("=" * 80)
    print("🎓 動画から学習")
    print("=" * 80)
    print()

    # システム初期化
    print("JCrossシステム初期化中...")
    baby = ZeroYearOldJCross()
    converter = MultiLayerCrossConverter(quality="fast")
    print("✅ 初期化完了")
    print()

    # 動画を開く
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"❌ 動画を開けませんでした: {video_path}")
        return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    print(f"📹 動画: {video_path.name}")
    print(f"   総フレーム: {total_frames}")
    print(f"   FPS: {fps:.2f}")
    print()

    print(f"設定:")
    print(f"  最大処理フレーム: {max_frames}")
    print(f"  スキップ: {skip_frames}フレームごと")
    print()

    # 学習データ
    frame_history = []
    prediction_stats = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "errors": []
    }
    discovered_patterns = []

    print("-" * 80)
    print()

    frame_count = 0
    processed_count = 0
    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        # スキップ
        if (frame_count - 1) % skip_frames != 0:
            continue

        # 最大フレーム数
        if processed_count >= max_frames:
            break

        # フレーム処理
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_resized = cv2.resize(frame_rgb, (64, 64))
        frame_pil = Image.fromarray(frame_resized)

        # Cross構造に変換
        cross_structure = converter.convert(frame_pil)

        # 履歴に追加
        frame_history.append({
            "frame": frame_count,
            "cross": cross_structure,
            "points": cross_structure['metadata']['total_points']
        })

        if len(frame_history) > 100:
            frame_history = frame_history[-100:]

        # 予測（3フレーム目以降）
        if len(frame_history) >= 3:
            prev_prev = frame_history[-3]
            prev = frame_history[-2]
            current = frame_history[-1]

            # 簡易予測: 点数の変化パターン
            prev_diff = prev['points'] - prev_prev['points']
            predicted_points = prev['points'] + prev_diff
            actual_points = current['points']

            error = abs(predicted_points - actual_points) / max(1, actual_points)

            prediction_stats["total"] += 1
            prediction_stats["errors"].append(error)

            if error < 0.05:
                prediction_stats["success"] += 1
            else:
                prediction_stats["failed"] += 1

                # 大きな誤差 = 新パターン
                if error > 0.2:
                    discovered_patterns.append({
                        "frame": frame_count,
                        "error": error,
                        "cross": cross_structure
                    })

        # 経験として保存
        discomfort_info = baby._calc_total_discomfort()
        baby._store_experience(
            cross_structure=cross_structure,
            discomfort=discomfort_info["総不快感"],
            context={"type": "ssd_video", "frame": frame_count}
        )

        processed_count += 1

        # 進捗表示
        if processed_count % 10 == 0:
            elapsed = time.time() - start_time
            fps_proc = processed_count / elapsed
            print(f"  処理: {processed_count}/{max_frames} " +
                  f"({processed_count/max_frames*100:.1f}%) " +
                  f"- {fps_proc:.1f} fps")

    cap.release()
    elapsed = time.time() - start_time

    print()
    print("-" * 80)
    print()

    # レポート
    print("=" * 80)
    print("📊 学習レポート")
    print("=" * 80)
    print()

    print("【動画情報】")
    print(f"  ファイル: {video_path.name}")
    print(f"  総フレーム: {total_frames}")
    print(f"  処理済み: {processed_count}")
    print(f"  処理時間: {elapsed:.2f}秒")
    print(f"  処理速度: {processed_count/elapsed:.2f} fps")
    print()

    print("【予測性能】")
    if prediction_stats["total"] > 0:
        success_rate = (prediction_stats["success"] / prediction_stats["total"]) * 100
        avg_error = np.mean(prediction_stats["errors"])

        print(f"  総予測回数: {prediction_stats['total']}")
        print(f"  成功: {prediction_stats['success']}")
        print(f"  失敗: {prediction_stats['failed']}")
        print(f"  成功率: {success_rate:.1f}%")
        print(f"  平均誤差: {avg_error:.4f}")

        # 緊張度の評価
        if avg_error < 0.05:
            print(f"  → 😌 理解している（規則的な動き）")
        elif avg_error < 0.15:
            print(f"  → 🤔 やや気になる（中程度の複雑さ）")
        else:
            print(f"  → 🔍 とても気になる！（不規則な動き）")
    else:
        print("  予測なし（フレーム数不足）")
    print()

    print("【パターン発見】")
    print(f"  発見パターン数: {len(discovered_patterns)}")
    if discovered_patterns:
        print(f"  最初の発見: フレーム {discovered_patterns[0]['frame']} " +
              f"(誤差={discovered_patterns[0]['error']:.3f})")
        print(f"  最後の発見: フレーム {discovered_patterns[-1]['frame']} " +
              f"(誤差={discovered_patterns[-1]['error']:.3f})")
    print()

    print("【記憶状態】")
    status = baby.get_status()
    print(f"  総経験数: {status['記憶']['総経験数']}")
    print(f"  クラスタ数: {status['記憶']['クラスタ数']}")
    print()

    print("【システム状態】")
    discomfort = baby._calc_total_discomfort()
    print(f"  現在の不快感: {discomfort['総不快感']:.3f}")
    print(f"  生存: {'✅' if baby._is_alive() else '❌'}")
    print()

    print("=" * 80)
    print()


def main():
    """メイン関数"""
    print()
    print("=" * 80)
    print("🎬 SSD内の動画から学習")
    print("=" * 80)
    print()

    # 検索パス
    search_paths = [
        Path.home() / "Desktop",
        Path.home() / "Downloads",
        Path.home() / "Movies",
        Path.home() / "Documents",
    ]

    print("動画ファイルを検索中...")
    videos = find_videos(search_paths)

    if not videos:
        print("❌ 動画ファイルが見つかりませんでした")
        return 1

    # 動画を選択
    selected_video = select_video(videos)

    if selected_video is None:
        print("キャンセルされました")
        return 0

    # 設定を入力
    print()
    print("=" * 80)
    print("⚙️  学習設定")
    print("=" * 80)
    print()

    try:
        max_frames = input("最大処理フレーム数 [100]: ").strip()
        max_frames = int(max_frames) if max_frames else 100

        skip_frames = input("スキップ（Nフレームごと） [5]: ").strip()
        skip_frames = int(skip_frames) if skip_frames else 5

    except ValueError:
        print("デフォルト値を使用します")
        max_frames = 100
        skip_frames = 5

    # 学習実行
    learn_from_video(selected_video, max_frames, skip_frames)

    print()
    print("=" * 80)
    print("🎉 完了")
    print("=" * 80)
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
