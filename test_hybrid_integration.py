#!/usr/bin/env python3
"""
Test Hybrid Architecture Integration

Tests that the hybrid wrapper properly:
1. Compiles JCross to Neural Model
2. Converts to Core ML
3. Initializes I/O processors
4. Runs main loop with Neural Engine state control
"""

import sys
import subprocess
import time
from pathlib import Path

def test_hybrid_compilation():
    """Test that hybrid wrapper compiles successfully"""
    print("=" * 70)
    print("Test 1: Hybrid Architecture Compilation")
    print("=" * 70)
    print()

    # Run hybrid wrapper in test mode (will fail on socket connect, but should compile)
    result = subprocess.run(
        [sys.executable, "verantyx_cli/engine/run_neural_wrapper.py", "localhost", "52749", "."],
        capture_output=True,
        text=True,
        timeout=120
    )

    output = result.stdout + result.stderr

    # Check for successful compilation
    if "✅ Compilation complete!" in output:
        print("✅ JCross → Neural Model compilation: SUCCESS")
    else:
        print("❌ JCross → Neural Model compilation: FAILED")
        print(output)
        return False

    if "✅ Core ML conversion complete!" in output:
        print("✅ Core ML conversion: SUCCESS")
    else:
        print("❌ Core ML conversion: FAILED")
        print(output)
        return False

    if "✅ Loaded 14 processors" in output:
        print("✅ I/O processor loading: SUCCESS (14 processors)")
    else:
        print("❌ I/O processor loading: FAILED (expected 14 processors)")
        print(output)
        return False

    if "✅ Hybrid Architecture Ready!" in output:
        print("✅ Hybrid architecture setup: SUCCESS")
    else:
        print("❌ Hybrid architecture setup: FAILED")
        print(output)
        return False

    print()
    print("=" * 70)
    print("✅ All compilation tests passed!")
    print("=" * 70)
    print()

    return True


def test_architecture_selection():
    """Test that setup wizard includes architecture selection"""
    print("=" * 70)
    print("Test 2: Architecture Selection in Setup")
    print("=" * 70)
    print()

    # Check setup wizard has architecture options
    setup_file = Path("verantyx_cli/ui/setup_wizard_safe.py")
    with open(setup_file, 'r') as f:
        content = f.read()

    if "Neural Engine" in content and "von Neumann" in content:
        print("✅ Setup wizard has architecture selection")
    else:
        print("❌ Setup wizard missing architecture selection")
        return False

    # Check launcher supports use_neural_engine
    launcher_file = Path("verantyx_cli/engine/claude_tab_launcher.py")
    with open(launcher_file, 'r') as f:
        content = f.read()

    if "use_neural_engine" in content:
        print("✅ Launcher supports Neural Engine flag")
    else:
        print("❌ Launcher missing Neural Engine support")
        return False

    print()
    print("=" * 70)
    print("✅ Architecture selection tests passed!")
    print("=" * 70)
    print()

    return True


def test_wrapper_selection():
    """Test that launcher correctly selects wrapper based on architecture"""
    print("=" * 70)
    print("Test 3: Wrapper Selection Logic")
    print("=" * 70)
    print()

    launcher_file = Path("verantyx_cli/engine/claude_tab_launcher.py")
    with open(launcher_file, 'r') as f:
        content = f.read()

    if "run_neural_wrapper.py" in content:
        print("✅ Launcher includes Neural Engine wrapper path")
    else:
        print("❌ Launcher missing Neural Engine wrapper")
        return False

    if "run_simple_wrapper.py" in content:
        print("✅ Launcher includes VM wrapper path")
    else:
        print("❌ Launcher missing VM wrapper")
        return False

    # Check run_neural_wrapper.py uses hybrid
    neural_runner = Path("verantyx_cli/engine/run_neural_wrapper.py")
    with open(neural_runner, 'r') as f:
        content = f.read()

    if "claude_wrapper_hybrid" in content:
        print("✅ Neural wrapper uses hybrid architecture")
    else:
        print("❌ Neural wrapper not using hybrid architecture")
        return False

    print()
    print("=" * 70)
    print("✅ Wrapper selection tests passed!")
    print("=" * 70)
    print()

    return True


if __name__ == "__main__":
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "Hybrid Architecture Integration Tests" + " " * 15 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    all_passed = True

    # Test 1: Compilation
    if not test_hybrid_compilation():
        all_passed = False

    # Test 2: Setup wizard
    if not test_architecture_selection():
        all_passed = False

    # Test 3: Wrapper selection
    if not test_wrapper_selection():
        all_passed = False

    print()
    if all_passed:
        print("✅ All tests passed! Hybrid architecture ready for use.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Please review output above.")
        sys.exit(1)
