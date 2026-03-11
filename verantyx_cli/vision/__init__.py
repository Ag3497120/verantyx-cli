"""
Vision module for Verantyx-CLI

Implements world-model-like Cross simulation for image recognition.
Converts images to Cross structure through point-based representation.
"""

from .image_to_cross import ImageToCross, convert_image_to_cross
from .cross_simulator import CrossSimulator, simulate_image_understanding, image_to_llm_context

__all__ = [
    "ImageToCross",
    "CrossSimulator",
    "convert_image_to_cross",
    "simulate_image_understanding",
    "image_to_llm_context",
]
