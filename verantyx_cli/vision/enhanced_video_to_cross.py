"""
Enhanced Video to Cross - 動画をCross構造に変換（形状認識付き）

各フレームでCross形状認識を実行し、動画内の「何が描画されているか」を理解
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
import numpy as np

logger = logging.getLogger(__name__)


def enhanced_video_to_llm_context(
    video_path: Path,
    max_frames: int = 10,
    use_shape_recognition: bool = True
) -> str:
    """
    動画をLLM可読コンテキストに変換（形状認識付き）

    Args:
        video_path: 動画ファイルパス
        max_frames: 最大フレーム数
        use_shape_recognition: Cross形状認識を使用するか

    Returns:
        LLM可読な動画の説明（形状認識結果を含む）
    """
    try:
        import cv2
    except ImportError:
        return f"[動画処理にはOpenCVが必要です: {video_path}]"

    # JCross形状認識をインポート
    if use_shape_recognition:
        try:
            from .run_shape_recognition import run_shape_recognition_on_image
            from PIL import Image
            import tempfile
        except ImportError as e:
            logger.warning(f"Shape recognition not available: {e}")
            use_shape_recognition = False

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

    logger.info(f"Video: {total_frames} frames, {fps:.2f} fps, {width}x{height}, {duration:.2f}s")

    # サンプリング間隔
    frame_interval = max(1, total_frames // max_frames)

    # フレームを処理
    frame_analyses = []
    frame_count = 0
    sampled_count = 0

    while sampled_count < max_frames:
        ret, frame = cap.read()

        if not ret:
            break

        if frame_count % frame_interval == 0:
            # BGR→RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            timestamp = frame_count / fps if fps > 0 else 0

            analysis = {
                "frame_number": frame_count,
                "timestamp": timestamp,
                "shapes": [],
                "details": ""
            }

            # Cross形状認識を実行
            if use_shape_recognition:
                try:
                    # 一時ファイルとして保存
                    pil_image = Image.fromarray(frame_rgb)
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                        tmp_path = Path(tmp.name)
                        pil_image.save(tmp_path)

                        # 形状認識を実行
                        shape_result = run_shape_recognition_on_image(tmp_path)

                        # 結果を追加
                        if "shape" in shape_result:
                            analysis["shapes"].append({
                                "shape": shape_result["shape"],
                                "confidence": shape_result.get("confidence", 0.0),
                                "point_count": shape_result.get("point_count", 0)
                            })

                        # 一時ファイル削除
                        tmp_path.unlink()

                except Exception as e:
                    logger.error(f"Shape recognition failed for frame {frame_count}: {e}")
                    analysis["details"] = f"[形状認識エラー: {e}]"

            frame_analyses.append(analysis)
            sampled_count += 1
            logger.info(f"Processed frame {frame_count}/{total_frames} (sample {sampled_count}/{max_frames})")

        frame_count += 1

    cap.release()

    # LLM可読コンテキスト構築
    llm_context = f"""# Enhanced Video Analysis: {video_path.name}

## Metadata
- Duration: {duration:.2f} seconds
- Frames: {total_frames} total, {len(frame_analyses)} analyzed
- FPS: {fps:.2f}
- Resolution: {width}x{height}
- Analysis: Cross Shape Recognition (JCross)

## Frame-by-Frame Analysis

"""

    for analysis in frame_analyses:
        timestamp = analysis["timestamp"]
        frame_num = analysis["frame_number"]

        llm_context += f"### Frame {frame_num} at {timestamp:.2f}s\n\n"

        # 形状認識結果
        if analysis["shapes"]:
            llm_context += "**Detected Shapes (Cross Recognition):**\n"
            for shape_data in analysis["shapes"]:
                shape = shape_data["shape"]
                conf = shape_data["confidence"]
                points = shape_data["point_count"]

                llm_context += f"- {shape} (confidence: {conf:.2f}, {points} Cross points)\n"
        else:
            llm_context += "**Detected Shapes:** None detected\n"

        if analysis["details"]:
            llm_context += f"\n{analysis['details']}\n"

        llm_context += "\n"

    llm_context += f"""## Summary

This video consists of {total_frames} frames over {duration:.2f} seconds.
Each frame was analyzed using Cross Shape Recognition (JCross implementation).
The analysis identified shapes based on Cross 6-axis point distribution patterns.

**Cross Shape Recognition Process:**
1. Image → Cross point cloud (each pixel mapped to 3D space)
2. Point positions measured with Cross 6-axis metrics (FRONT/BACK/UP/DOWN/RIGHT/LEFT)
3. Distribution patterns extracted from Cross point cloud
4. Patterns matched against shape memory (fragment memory)
5. Recognized shapes returned with confidence scores

This allows understanding of **what is actually drawn** in the video frames.
"""

    return llm_context


def convert_video_to_cross_enhanced(
    video_path: Path,
    output_path: Optional[Path] = None,
    max_frames: int = 30,
    quality: str = "maximum",
    use_shape_recognition: bool = True
) -> dict:
    """
    動画をCross構造に変換（形状認識付き）

    Args:
        video_path: 動画ファイルパス
        output_path: 出力パス
        max_frames: 最大フレーム数
        quality: 品質（maximum固定）
        use_shape_recognition: JCross形状認識を使用するか

    Returns:
        Cross構造（形状認識結果を含む）
    """
    try:
        import cv2
    except ImportError:
        logger.error("OpenCV not installed. Install with: pip install opencv-python")
        raise ImportError("opencv-python is required for video processing")

    from .video_to_cross import VideoToCross

    logger.info(f"Converting video to Cross with shape recognition: {video_path}")

    # 基本のCross変換
    converter = VideoToCross()
    cross_structure = converter.convert(video_path, output_path=None, max_frames=max_frames, quality=quality)

    # 形状認識を追加
    if use_shape_recognition:
        try:
            from .run_shape_recognition import run_shape_recognition_on_image
            from PIL import Image
            import tempfile

            cap = cv2.VideoCapture(str(video_path))

            if cap.isOpened():
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_interval = max(1, total_frames // max_frames)

                shape_recognitions = []
                frame_count = 0
                sampled_count = 0

                while sampled_count < max_frames:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    if frame_count % frame_interval == 0:
                        # BGR→RGB
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        pil_image = Image.fromarray(frame_rgb)

                        # 一時ファイルに保存
                        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                            tmp_path = Path(tmp.name)
                            pil_image.save(tmp_path)

                            # 形状認識
                            shape_result = run_shape_recognition_on_image(tmp_path)

                            timestamp = frame_count / fps if fps > 0 else 0
                            shape_recognitions.append({
                                "frame_number": frame_count,
                                "timestamp": timestamp,
                                "recognition": shape_result
                            })

                            tmp_path.unlink()

                        sampled_count += 1

                    frame_count += 1

                cap.release()

                # Cross構造に形状認識を追加
                cross_structure["shape_recognition"] = {
                    "enabled": True,
                    "method": "JCross Cross 6-axis pattern matching",
                    "frames": shape_recognitions
                }

        except Exception as e:
            logger.error(f"Shape recognition failed: {e}")
            cross_structure["shape_recognition"] = {
                "enabled": False,
                "error": str(e)
            }

    # 保存
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(cross_structure, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved enhanced video Cross structure: {output_path}")

    return cross_structure
