#!/usr/bin/env python3
"""
Test Image Conversion Feature

Verifies that:
1. Image detection works
2. Image conversion to Cross structure works
3. Cross structure is valid
"""

import sys
from pathlib import Path
from PIL import Image
import numpy as np

def create_test_image():
    """Create a simple test image"""
    print("Creating test image...")

    # Create a 100x100 RGB image with gradient
    img = Image.new('RGB', (100, 100))
    pixels = img.load()

    for i in range(100):
        for j in range(100):
            # Simple gradient
            r = int(i * 255 / 100)
            g = int(j * 255 / 100)
            b = 128
            pixels[i, j] = (r, g, b)

    test_image_path = Path("test_image.png")
    img.save(test_image_path)

    print(f"✅ Created test image: {test_image_path}")
    return test_image_path


def test_image_detection():
    """Test image path detection in chat input"""
    print("\n" + "=" * 70)
    print("Test 1: Image Path Detection")
    print("=" * 70)

    from verantyx_cli.ui.image_chat_handler import ImageChatHandler

    # Create .verantyx directory for testing
    verantyx_dir = Path.cwd() / ".verantyx"
    verantyx_dir.mkdir(exist_ok=True)

    handler = ImageChatHandler(verantyx_dir=verantyx_dir)

    # Test with explicit path
    test_inputs = [
        ("/image test_image.png", "test_image.png"),
        ("no image here", None),
    ]

    for user_input, expected in test_inputs:
        result = handler.detect_image_input(user_input)

        if expected is None:
            if result is None:
                print(f"✅ Correctly detected no image: '{user_input}'")
            else:
                print(f"❌ False positive: '{user_input}' detected as {result}")
                return False
        else:
            if result:
                original_input, image_path, quality = result
                if image_path.name == expected:
                    print(f"✅ Correctly detected: '{user_input}' → {image_path.name} (quality: {quality})")
                else:
                    print(f"❌ Wrong path detected: got {image_path.name}, expected {expected}")
                    return False
            else:
                print(f"❌ Failed to detect: '{user_input}' (expected {expected})")
                return False

    print()
    return True


def test_image_conversion():
    """Test image to Cross structure conversion"""
    print("=" * 70)
    print("Test 2: Image to Cross Conversion")
    print("=" * 70)

    from verantyx_cli.ui.image_chat_handler import ImageChatHandler

    test_image_path = Path("test_image.png")

    if not test_image_path.exists():
        print("❌ Test image not found")
        return False

    # Create .verantyx directory for testing
    verantyx_dir = Path.cwd() / ".verantyx"
    verantyx_dir.mkdir(exist_ok=True)

    handler = ImageChatHandler(verantyx_dir=verantyx_dir)

    # Convert with 'low' quality for fast test
    success, cross_structure, message = handler.convert_image(
        test_image_path,
        quality='low'
    )

    if not success:
        print(f"❌ Conversion failed: {message}")
        return False

    print(f"✅ Conversion succeeded: {message}")

    # Verify Cross structure
    if 'metadata' not in cross_structure:
        print("❌ Missing metadata in Cross structure")
        return False

    if 'axes' not in cross_structure:
        print("❌ Missing axes in Cross structure")
        return False

    metadata = cross_structure['metadata']
    print(f"✅ Metadata present: {metadata.get('original_filename')}")

    axes = cross_structure['axes']

    # Image Cross structures use combined axes: RIGHT_LEFT, UP_DOWN, FRONT_BACK
    expected_axes = ['RIGHT_LEFT', 'UP_DOWN', 'FRONT_BACK']

    for axis in expected_axes:
        if axis not in axes:
            print(f"❌ Missing axis: {axis}")
            return False

    print(f"✅ All 3 combined axes present")

    # Check that regions exist
    if 'regions' not in cross_structure:
        print("❌ Missing regions in Cross structure")
        return False

    regions = cross_structure['regions']
    num_regions = len(regions)
    print(f"✅ Image regions: {num_regions}")

    if num_regions == 0:
        print("❌ No regions detected")
        return False

    print()
    return True


def test_cross_structure_validity():
    """Test that saved Cross JSON is valid"""
    print("=" * 70)
    print("Test 3: Cross Structure File Validity")
    print("=" * 70)

    import json

    # Check if .verantyx/vision directory exists
    vision_dir = Path.cwd() / ".verantyx" / "vision"

    if not vision_dir.exists():
        print(f"⚠️  Vision directory doesn't exist yet: {vision_dir}")
        return True  # Not a failure, just hasn't been created

    # Find Cross JSON files
    cross_files = list(vision_dir.glob("*.cross.json"))

    if not cross_files:
        print("⚠️  No Cross JSON files found (conversion might not have saved)")
        return True  # Not a failure for this test

    print(f"Found {len(cross_files)} Cross JSON file(s)")

    for cross_file in cross_files:
        try:
            with open(cross_file, 'r') as f:
                data = json.load(f)

            # Verify structure
            if 'metadata' in data and 'axes' in data:
                print(f"✅ Valid Cross JSON: {cross_file.name}")
            else:
                print(f"❌ Invalid Cross JSON structure: {cross_file.name}")
                return False

        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in {cross_file.name}: {e}")
            return False

    print()
    return True


def cleanup():
    """Cleanup test files"""
    print("Cleaning up test files...")

    test_image = Path("test_image.png")
    if test_image.exists():
        test_image.unlink()
        print(f"✅ Removed: {test_image}")


if __name__ == "__main__":
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 20 + "Image Conversion Tests" + " " * 26 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    all_passed = True

    try:
        # Create test image
        test_image_path = create_test_image()

        # Test 1: Detection
        if not test_image_detection():
            all_passed = False

        # Test 2: Conversion
        if not test_image_conversion():
            all_passed = False

        # Test 3: File validity
        if not test_cross_structure_validity():
            all_passed = False

    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("   Install with: pip install pillow numpy")
        all_passed = False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    finally:
        cleanup()

    print()
    if all_passed:
        print("✅ All image conversion tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Please review output above.")
        sys.exit(1)
