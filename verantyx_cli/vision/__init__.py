"""
Vision module for Verantyx-CLI

Implements world-model-like Cross simulation for image and video recognition.
Converts visual media to Cross structure through point-based representation.

## Cross Shape Recognition (JCross)
- Points are mapped from pixels to 3D space
- Each point's position measured with Cross 6-axis (FRONT/BACK/UP/DOWN/RIGHT/LEFT)
- Distribution patterns extracted from Cross point cloud
- Patterns matched against shape memory (fragment memory)
- Recognized shapes based on Cross point arrangement
"""

from .image_to_cross import ImageToCross, convert_image_to_cross
from .cross_simulator import CrossSimulator, simulate_image_understanding, image_to_llm_context
from .video_to_cross import VideoToCross, convert_video_to_cross, video_to_llm_context

# Enhanced with JCross shape recognition
from .enhanced_video_to_cross import (
    enhanced_video_to_llm_context,
    convert_video_to_cross_enhanced
)

from .vision_processors import create_vision_processors

__all__ = [
    # Basic Cross conversion
    "ImageToCross",
    "CrossSimulator",
    "VideoToCross",
    "convert_image_to_cross",
    "convert_video_to_cross",
    "simulate_image_understanding",
    "image_to_llm_context",
    "video_to_llm_context",

    # Enhanced with shape recognition
    "enhanced_video_to_llm_context",
    "convert_video_to_cross_enhanced",
    "create_vision_processors",
]
