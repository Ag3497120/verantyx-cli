"""
CLI command handlers for memory, config, and vision management
"""

import json
from pathlib import Path
from typing import Optional


def get_verantyx_dir() -> Path:
    """Get Verantyx directory (~/.verantyx)"""
    verantyx_dir = Path.home() / ".verantyx"
    verantyx_dir.mkdir(exist_ok=True)
    return verantyx_dir


def handle_memory_command(command: str):
    """Handle memory subcommands"""
    verantyx_dir = get_verantyx_dir()
    memory_file = verantyx_dir / "cross_memory.json"

    if command == "show":
        if not memory_file.exists():
            print("❌ No Cross Memory found. Start using Verantyx to build memory.")
            return

        with open(memory_file, 'r') as f:
            memory_data = json.load(f)

        print("\n" + "=" * 70)
        print("🧠 Cross Memory Contents")
        print("=" * 70)
        print(f"\nMemory file: {memory_file}")
        print(f"Total entries: {len(memory_data.get('knowledge', []))}")
        print("\nRecent entries:")

        for entry in memory_data.get('knowledge', [])[-10:]:
            name = entry.get('name', 'Unknown')
            axis = entry.get('axis', 'N/A')
            print(f"  • {name} (axis: {axis})")

    elif command == "stats":
        if not memory_file.exists():
            print("❌ No Cross Memory found.")
            return

        with open(memory_file, 'r') as f:
            memory_data = json.load(f)

        knowledge = memory_data.get('knowledge', [])

        print("\n" + "=" * 70)
        print("📊 Cross Memory Statistics")
        print("=" * 70)
        print(f"\nTotal knowledge items: {len(knowledge)}")

        # Count by axis
        axis_counts = {}
        for entry in knowledge:
            axis = entry.get('axis', 'unknown')
            axis_counts[axis] = axis_counts.get(axis, 0) + 1

        print("\nKnowledge by axis:")
        axis_names = {0: "UP", 1: "DOWN", 2: "FRONT", 3: "BACK", 4: "RIGHT", 5: "LEFT"}
        for axis, count in sorted(axis_counts.items()):
            axis_name = axis_names.get(axis, f"Axis {axis}")
            print(f"  • {axis_name}: {count}")

    elif command == "clear":
        if memory_file.exists():
            confirm = input("⚠️  Clear all Cross Memory? This cannot be undone. (yes/no): ")
            if confirm.lower() == "yes":
                memory_file.unlink()
                print("✅ Cross Memory cleared")
            else:
                print("Cancelled")
        else:
            print("❌ No Cross Memory to clear")


def handle_config_command(command: str):
    """Handle config subcommands"""
    verantyx_dir = get_verantyx_dir()
    config_file = verantyx_dir / "config.yaml"

    if command == "init":
        if config_file.exists():
            confirm = input("⚠️  Config file already exists. Overwrite? (yes/no): ")
            if confirm.lower() != "yes":
                print("Cancelled")
                return

        # Create default config
        default_config = """# Verantyx-CLI Configuration

# LLM Settings
llm:
  primary: claude
  fallback: gemini

  claude:
    api_key: ${ANTHROPIC_API_KEY}
    model: claude-sonnet-4.5
    max_tokens: 8192

  gemini:
    api_key: ${GOOGLE_API_KEY}
    model: gemini-2.0-flash-exp

  ollama:
    host: http://localhost:11434
    model: qwen2.5-coder:32b

# UI Settings
ui:
  theme: monokai
  show_thinking: true
  auto_scroll: true

# Autonomy Settings
autonomy:
  enabled: true
  max_tasks_parallel: 3
  auto_commit: false

# Learning Settings
learning:
  enabled: true
  pattern_learning: true
  user_profiling: true
"""

        with open(config_file, 'w') as f:
            f.write(default_config)

        print(f"✅ Config initialized: {config_file}")
        print("\n⚠️  Remember to set API keys:")
        print("   export ANTHROPIC_API_KEY='your-key'")
        print("   export GOOGLE_API_KEY='your-key'")

    elif command == "show":
        if not config_file.exists():
            print("❌ No config file. Run 'verantyx config init' first.")
            return

        with open(config_file, 'r') as f:
            config = f.read()

        print("\n" + "=" * 70)
        print("⚙️  Verantyx Configuration")
        print("=" * 70)
        print(f"\nFile: {config_file}\n")
        print(config)

    elif command == "edit":
        if not config_file.exists():
            print("❌ No config file. Run 'verantyx config init' first.")
            return

        import os
        editor = os.environ.get('EDITOR', 'nano')
        os.system(f"{editor} {config_file}")
        print("✅ Config edited")


def handle_vision_command(
    image_path: str,
    output_path: Optional[str] = None,
    llm_context: bool = False,
    quality: str = "medium",
    max_points: Optional[int] = None
):
    """
    Handle vision command - convert image to Cross structure

    Args:
        image_path: Path to image file
        output_path: Optional output path for Cross structure
        llm_context: If True, generate LLM-readable context
        quality: Quality preset ('low', 'medium', 'high', 'ultra', 'maximum')
        max_points: Custom max points (overrides quality)
    """
    try:
        from .vision import convert_image_to_cross, image_to_llm_context, ImageToCross

        img_path = Path(image_path)

        if not img_path.exists():
            print(f"❌ Image not found: {image_path}")
            return 1

        # Display quality info
        if max_points:
            print(f"🖼️  Processing image: {img_path.name} (custom: {max_points:,} points)")
        else:
            quality_info = ImageToCross.QUALITY_PRESETS.get(quality, {})
            points = quality_info.get('max_points', 1000)
            print(f"🖼️  Processing image: {img_path.name} (quality: {quality}, {points:,} points)")
        print()

        if llm_context:
            # Generate LLM context
            print("🧠 Generating LLM-readable context via Cross simulation...")
            context = image_to_llm_context(img_path)
            print()
            print("=" * 70)
            print(context)
            print("=" * 70)
            print()

        else:
            # Convert to Cross structure
            print("🔄 Converting image to Cross structure...")
            import time
            start_time = time.time()

            cross_structure = convert_image_to_cross(
                image_path=img_path,
                output_path=Path(output_path) if output_path else None,
                quality=quality,
                max_points=max_points
            )

            elapsed = time.time() - start_time

            print()
            print(f"✅ Conversion complete! ({elapsed:.2f}s)")
            print()
            print(f"📊 Cross Structure Summary:")
            print(f"   - Image: {img_path.name}")
            print(f"   - Size: {cross_structure['metadata']['original_size']}")
            print(f"   - Points: {cross_structure['metadata']['num_points']:,}")
            print(f"   - Regions: {cross_structure['metadata']['num_regions']}")
            print(f"   - Processing time: {elapsed:.2f}s")
            print()

            if output_path:
                print(f"💾 Saved to: {output_path}")
            else:
                # Print JSON
                print("Cross Structure:")
                print(json.dumps(cross_structure, indent=2))

        return 0

    except ImportError as e:
        print("❌ Vision support not available")
        print("   Install with: pip install pillow numpy")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
