#!/usr/bin/env python3
"""
Test script for ImageChatHandler
"""

from pathlib import Path
from verantyx_cli.ui.image_chat_handler import ImageChatHandler

# Setup
verantyx_dir = Path.home() / '.verantyx_test'
verantyx_dir.mkdir(exist_ok=True)

handler = ImageChatHandler(verantyx_dir)

# Test inputs
test_inputs = [
    "/Users/motonishikoudai/Downloads/IMG_9278.DNG high",
    "/image /Users/motonishikoudai/Downloads/IMG_9278.DNG high",
    "/Users/motonishikoudai/Downloads/IMG_9278.DNG",
]

print("Testing ImageChatHandler...")
print("=" * 70)

for test_input in test_inputs:
    print(f"\nInput: {test_input}")
    print("-" * 70)

    # Detect
    detection = handler.detect_image_input(test_input)
    if detection:
        print(f"✅ Detected: {detection}")
        command_type, image_path, quality = detection

        # Process
        processed_message, cross_structure = handler.process_input(test_input)
        print(f"\nProcessed Message:\n{processed_message[:500]}...")

        if cross_structure:
            print(f"\n✅ Cross structure generated!")
            print(f"   Points: {cross_structure['metadata']['num_points']}")
            print(f"   Regions: {cross_structure['metadata']['num_regions']}")
    else:
        print(f"❌ Not detected")

    print()

print("=" * 70)
print("Test complete!")
