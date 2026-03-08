"""
Image Chat Handler - Handle image inputs in chat

Detects image file paths in user input and automatically converts them to Cross structures.
Supports:
- Direct file paths: /path/to/image.jpg
- Drag & drop simulation: User pastes path from file manager
- /image command: /image <path> [quality]
"""

import re
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ImageChatHandler:
    """
    Handle image inputs in chat interface

    Detects when user provides an image path and converts to Cross structure.
    """

    # Supported image extensions
    IMAGE_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif',
        '.dng', '.raw', '.cr2', '.nef', '.arw', '.orf'  # RAW formats
    }

    # Patterns to detect image paths (case-insensitive)
    IMAGE_PATH_PATTERNS = [
        r'/image\s+([^\s]+)(?:\s+(low|medium|high|ultra|maximum))?',  # /image command
        r'(?:^|\s)([~/][\w/._-]+\.(?:jpe?g|png|gif|bmp|webp|tiff?|dng|raw|cr2|nef|arw|orf))(?:\s+(low|medium|high|ultra|maximum))?(?:\s|$)',  # Unix path with optional quality
        r'(?:^|\s)([A-Za-z]:[\\\/][\w\\\/._-]+\.(?:jpe?g|png|gif|bmp|webp|tiff?|dng|raw|cr2|nef|arw|orf))(?:\s+(low|medium|high|ultra|maximum))?(?:\s|$)',  # Windows path with optional quality
    ]

    def __init__(self, verantyx_dir: Path):
        """
        Initialize image handler

        Args:
            verantyx_dir: Directory to store converted Cross structures
        """
        self.verantyx_dir = verantyx_dir
        self.vision_dir = verantyx_dir / "vision"
        self.vision_dir.mkdir(exist_ok=True)

        # Check if vision support is available
        try:
            from verantyx_cli.vision.image_to_cross import VISION_AVAILABLE
            self.vision_available = VISION_AVAILABLE
        except ImportError:
            self.vision_available = False
            logger.warning("Vision support not available. Install: pip install pillow numpy")

    def detect_image_input(self, user_input: str) -> Optional[Tuple[str, Path, str]]:
        """
        Detect if user input contains an image path

        Args:
            user_input: User's input message

        Returns:
            Tuple of (command_type, image_path, quality) if detected, None otherwise
            command_type: 'explicit' (used /image) or 'implicit' (just pasted path)
        """
        logger.debug(f"Detecting image in input: {user_input[:100]}...")

        # Try each pattern
        for pattern in self.IMAGE_PATH_PATTERNS:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                groups = match.groups()
                logger.debug(f"Pattern matched: {pattern}, groups: {groups}")

                # Check if it's /image command
                if pattern.startswith(r'/image'):
                    image_path_str = groups[0]
                    quality = groups[1] if len(groups) > 1 and groups[1] else 'medium'
                    command_type = 'explicit'
                else:
                    # For path-based patterns, quality is in groups[1]
                    image_path_str = groups[0]
                    quality = groups[1] if len(groups) > 1 and groups[1] else 'medium'
                    command_type = 'implicit'

                # Expand ~ and resolve path
                image_path = Path(image_path_str).expanduser().resolve()
                logger.debug(f"Resolved path: {image_path}, exists: {image_path.exists()}, suffix: {image_path.suffix.lower()}")

                # Verify it exists and is an image
                if image_path.exists() and image_path.suffix.lower() in self.IMAGE_EXTENSIONS:
                    logger.info(f"Image detected: {image_path} (type: {command_type}, quality: {quality})")
                    return (command_type, image_path, quality)
                else:
                    if not image_path.exists():
                        logger.warning(f"Path matched but file not found: {image_path}")
                    elif image_path.suffix.lower() not in self.IMAGE_EXTENSIONS:
                        logger.warning(f"Path matched but unsupported format: {image_path.suffix}")

        logger.debug("No image detected in input")
        return None

    def convert_image(
        self,
        image_path: Path,
        quality: str = 'medium'
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Convert image to Cross structure

        Args:
            image_path: Path to image file
            quality: Quality preset ('low', 'medium', 'high', 'ultra', 'maximum')

        Returns:
            Tuple of (success, cross_structure, message)
        """
        if not self.vision_available:
            return (
                False,
                {},
                "❌ Vision support not available. Install: pip install pillow numpy"
            )

        if not image_path.exists():
            return (False, {}, f"❌ Image not found: {image_path}")

        if image_path.suffix.lower() not in self.IMAGE_EXTENSIONS:
            return (False, {}, f"❌ Unsupported image format: {image_path.suffix}")

        try:
            from verantyx_cli.vision.image_to_cross import convert_image_to_cross

            # Output path
            output_filename = f"{image_path.stem}.cross.json"
            output_path = self.vision_dir / output_filename

            # Convert
            logger.info(f"Converting image: {image_path} (quality: {quality})")
            print(f"\n🔄 Converting image: {image_path.name} (quality: {quality})...")

            cross_structure = convert_image_to_cross(
                image_path=image_path,
                output_path=output_path,
                quality=quality
            )

            # Build success message (short to avoid paste mode)
            num_points = cross_structure['metadata']['num_points']
            num_regions = cross_structure['metadata']['num_regions']

            message = (
                f"Image {image_path.name} converted: {num_regions} regions, {num_points:,} points. "
                f"Cross file: {output_path.relative_to(self.verantyx_dir.parent)}"
            )

            return (True, cross_structure, message)

        except ImportError as e:
            error_msg = f"❌ Failed to import image conversion module: {str(e)}\n\nInstall required packages: pip install pillow numpy"
            logger.error(error_msg, exc_info=True)
            return (False, {}, error_msg)
        except Exception as e:
            error_msg = f"❌ Failed to convert image: {str(e)}\n\nImage: {image_path}\nQuality: {quality}\n\nCheck if the image file is valid and not corrupted."
            logger.error(f"Image conversion error: {e}", exc_info=True)
            return (False, {}, error_msg)

    def process_input(self, user_input: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Process user input, detecting and converting images if present

        Args:
            user_input: User's input message

        Returns:
            Tuple of (processed_message, cross_structure)
            - processed_message: Message to send to Claude (may include Cross structure info)
            - cross_structure: Cross structure if image was converted, None otherwise
        """
        # Detect image input
        detection = self.detect_image_input(user_input)

        if detection is None:
            # No image detected, pass through
            return (user_input, None)

        command_type, image_path, quality = detection

        # Convert image
        success, cross_structure, message = self.convert_image(image_path, quality)

        if not success:
            # Conversion failed, return error message
            return (message, None)

        # Build enhanced message for Claude (keep short)
        if command_type == 'explicit':
            # User explicitly asked to convert with /image
            processed_message = message
        else:
            # User pasted path, add context
            # Remove image path and quality from original text
            original_text = user_input.replace(str(image_path), '').strip()
            # Also remove quality keywords if present
            for qual in ['low', 'medium', 'high', 'ultra', 'maximum']:
                original_text = original_text.replace(qual, '').strip()

            if original_text:
                processed_message = f"{message} Question: {original_text}"
            else:
                processed_message = message

        return (processed_message, cross_structure)

    def get_help_text(self) -> str:
        """Get help text for image commands"""
        if not self.vision_available:
            return (
                "🖼️  **Image Support (Not Available)**\n\n"
                "Install vision support: `pip install pillow numpy`"
            )

        return (
            "🖼️  **Image Support**\n\n"
            "**Methods to convert images:**\n\n"
            "1. **Command:** `/image <path> [quality]`\n"
            "   Example: `/image ~/photos/sunset.jpg high`\n\n"
            "2. **Drag & Drop (paste path):** Just paste the image file path\n"
            "   Example: `/Users/name/Desktop/image.png`\n\n"
            "**Quality levels:** low, medium (default), high, ultra, maximum\n\n"
            "**Supported formats:** JPG, PNG, GIF, BMP, WebP, TIFF\n\n"
            "**Cross structure output:**\n"
            "- 6-axis representation (RIGHT/LEFT, UP/DOWN, FRONT/BACK)\n"
            "- Region detection with patterns\n"
            "- Spatial relationships\n"
            "- Saved to `.verantyx/vision/`\n"
        )
