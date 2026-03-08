"""
Video to Cross - 動画をCross構造に変換

動画をフレームごとに解析してCross構造に変換し、
時間軸を含む4次元（3D空間+時間）の視覚情報として表現する。
"""

import logging
from pathlib import Path
from typing import Optional, List
import json

logger = logging.getLogger(__name__)


class VideoToCross:
    """
    動画をCross構造に変換

    アプローチ:
    1. 動画をフレームに分割
    2. 各フレームをCross構造に変換
    3. 時間軸を追加してCross構造を拡張
    """

    def __init__(self):
        self.supported_formats = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv']

    def is_video(self, file_path: Path) -> bool:
        """ファイルが動画かチェック"""
        return file_path.suffix.lower() in self.supported_formats

    def convert(
        self,
        video_path: Path,
        output_path: Optional[Path] = None,
        max_frames: int = 30,
        quality: str = "maximum"
    ) -> dict:
        """
        動画をCross構造に変換

        Args:
            video_path: 動画ファイルパス
            output_path: 出力パス（Noneの場合は返すだけ）
            max_frames: 最大フレーム数（均等サンプリング）
            quality: 品質（maximum固定）

        Returns:
            Cross構造
        """
        try:
            import cv2
        except ImportError:
            logger.error("OpenCV not installed. Install with: pip install opencv-python")
            raise ImportError("opencv-python is required for video processing")

        from .image_to_cross import ImageToCross

        logger.info(f"Converting video to Cross: {video_path}")

        # 動画を開く
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            raise ValueError(f"Failed to open video: {video_path}")

        # 動画情報を取得
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0

        logger.info(f"Video info: {total_frames} frames, {fps:.2f} fps, {width}x{height}, {duration:.2f}s")

        # サンプリング間隔を計算
        if total_frames > max_frames:
            frame_interval = total_frames // max_frames
        else:
            frame_interval = 1
            max_frames = total_frames

        # 各フレームを処理
        frames_cross = []
        frame_count = 0
        sampled_count = 0

        image_converter = ImageToCross()

        while True:
            ret, frame = cap.read()

            if not ret:
                break

            # サンプリング
            if frame_count % frame_interval == 0 and sampled_count < max_frames:
                # BGRからRGBに変換
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # PIL Imageに変換
                from PIL import Image
                import numpy as np
                pil_image = Image.fromarray(frame_rgb)

                # Crossに変換（maximum品質）
                frame_cross = image_converter.convert_image(
                    pil_image,
                    quality="maximum"
                )

                # タイムスタンプを追加
                timestamp = frame_count / fps if fps > 0 else 0

                frames_cross.append({
                    "frame_number": frame_count,
                    "timestamp": timestamp,
                    "cross_structure": frame_cross
                })

                sampled_count += 1
                logger.info(f"Processed frame {frame_count}/{total_frames} (sample {sampled_count}/{max_frames})")

            frame_count += 1

        cap.release()

        # Cross構造を構築
        cross_structure = {
            "version": "1.0",
            "type": "video",
            "metadata": {
                "source": str(video_path.name),
                "total_frames": total_frames,
                "sampled_frames": len(frames_cross),
                "fps": fps,
                "duration": duration,
                "resolution": f"{width}x{height}",
                "quality": quality
            },
            "axes": {
                "TIME": {
                    "frames": frames_cross,
                    "total_frames": len(frames_cross),
                    "duration": duration
                }
            }
        }

        # 保存
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(cross_structure, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved video Cross structure: {output_path}")

        return cross_structure


def video_to_llm_context(video_path: Path, max_frames: int = 10) -> str:
    """
    動画をLLM可読コンテキストに変換

    Args:
        video_path: 動画ファイルパス
        max_frames: 最大フレーム数

    Returns:
        LLM可読な動画の説明
    """
    from .cross_simulator import image_to_llm_context

    try:
        import cv2
    except ImportError:
        return f"[動画処理にはOpenCVが必要です: {video_path}]"

    # 動画を開く
    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        return f"[動画を開けませんでした: {video_path}]"

    # 動画情報
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = total_frames / fps if fps > 0 else 0

    # サンプリング間隔
    frame_interval = max(1, total_frames // max_frames)

    # フレームを処理
    frame_descriptions = []
    frame_count = 0
    sampled_count = 0

    while sampled_count < max_frames:
        ret, frame = cap.read()

        if not ret:
            break

        if frame_count % frame_interval == 0:
            # BGR→RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # PIL Image
            from PIL import Image
            pil_image = Image.fromarray(frame_rgb)

            # 一時ファイルとして保存
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp_path = Path(tmp.name)
                pil_image.save(tmp_path)

                # LLMコンテキスト生成
                context = image_to_llm_context(tmp_path)

                timestamp = frame_count / fps if fps > 0 else 0
                frame_descriptions.append(
                    f"[Frame {frame_count} at {timestamp:.2f}s]\n{context}\n"
                )

                # 一時ファイル削除
                tmp_path.unlink()

            sampled_count += 1

        frame_count += 1

    cap.release()

    # LLM可読コンテキスト構築
    llm_context = f"""# Video Analysis: {video_path.name}

## Metadata
- Duration: {duration:.2f} seconds
- Frames: {total_frames} total, {len(frame_descriptions)} analyzed
- FPS: {fps:.2f}
- Resolution: {width}x{height}

## Frame-by-Frame Analysis

{chr(10).join(frame_descriptions)}

## Summary
This video consists of {total_frames} frames over {duration:.2f} seconds.
Above is the analysis of {len(frame_descriptions)} key frames sampled uniformly throughout the video.
"""

    return llm_context


def convert_video_to_cross(
    video_path: Path,
    output_path: Optional[Path] = None,
    max_frames: int = 30,
    quality: str = "maximum"
) -> dict:
    """
    動画をCross構造に変換（ショートカット関数）

    Args:
        video_path: 動画ファイルパス
        output_path: 出力パス
        max_frames: 最大フレーム数
        quality: 品質

    Returns:
        Cross構造
    """
    converter = VideoToCross()
    return converter.convert(video_path, output_path, max_frames, quality)
