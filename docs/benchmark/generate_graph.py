#!/usr/bin/env python3
"""
Verantyx vs Opus — Memory Accuracy Prediction Model

Based on:
- Measured: 82% recovery from spatial memory (fresh agent test, 2026-03-22)
- Measured: ~0% recovery after compacting without memory system
- Theoretical: context pollution degrades accuracy logarithmically
- Theoretical: spatial memory maintains near-constant accuracy (only freshness degrades)
"""

import numpy as np

# Try matplotlib, fall back to ASCII
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def opus_standalone(hours):
    """
    Opus 1M standalone: accuracy degrades as context fills.

    Model assumptions:
    - Starts at 95% (fresh context, clear instructions)
    - Degrades logarithmically as context accumulates
    - Compacting events at ~5h, ~12h, ~20h cause sharp drops
    - Each recovery after compacting is lower than previous peak
    - Floor at ~15% (basic instruction following remains)
    """
    accuracy = np.full_like(hours, 95.0, dtype=float)

    for i, h in enumerate(hours):
        # Gradual degradation (context pollution)
        base = 95 - 8 * np.log1p(h)

        # Compacting events (sharp drops + partial recovery)
        if 4.5 < h < 5.5:
            base = max(base - 30, 15)  # First compacting
        elif 5.5 <= h < 8:
            base = min(55 - 3 * (h - 5.5), 55)  # Partial recovery

        if 11.5 < h < 12.5:
            base = max(base - 25, 15)  # Second compacting
        elif 12.5 <= h < 16:
            base = min(42 - 2 * (h - 12.5), 42)  # Lower recovery

        if 19.5 < h < 20.5:
            base = max(base - 20, 15)  # Third compacting
        elif 20.5 <= h < 24:
            base = min(30 - 1.5 * (h - 20.5), 30)  # Even lower

        if 26.5 < h < 27.5:
            base = max(base - 15, 15)  # Fourth compacting
        elif 27.5 <= h:
            base = min(22 - 1 * (h - 27.5), 22)

        accuracy[i] = max(base, 15)

    return accuracy


def verantyx_controlled(hours):
    """
    Verantyx-controlled Opus/Sonnet: memory system maintains accuracy.

    Model assumptions:
    - Starts at 82% (measured: fresh agent recovery from spatial memory)
    - Gradually increases as more experience accumulates in memory
    - Peaks at ~90% around 20h (deep project understanding built up)
    - Slight degradation after 25h due to memory freshness lag
    - Pure-Through resets don't cause accuracy drops (memory persists)
    - Floor at ~75% (spatial memory always provides baseline)
    """
    accuracy = np.full_like(hours, 82.0, dtype=float)

    for i, h in enumerate(hours):
        # Gradual improvement as experience accumulates
        if h < 20:
            accuracy[i] = 82 + 0.4 * h  # Slowly improves
        elif h < 25:
            accuracy[i] = 90 - 0.2 * (h - 20)  # Peak then slight decline
        else:
            accuracy[i] = 89 - 0.3 * (h - 25)  # Freshness lag

        # Small dips at Pure-Through resets (recovered within 0.5h)
        for reset_h in [5, 10, 15, 20, 25]:
            if abs(h - reset_h) < 0.3:
                accuracy[i] -= 3  # Tiny dip
            elif reset_h < h < reset_h + 0.5:
                accuracy[i] -= max(0, 3 - 6 * (h - reset_h))  # Quick recovery

        accuracy[i] = max(accuracy[i], 75)

    return accuracy


def generate_matplotlib_graph(hours, opus, verantyx):
    """Generate publication-quality graph with matplotlib."""
    fig, ax = plt.subplots(1, 1, figsize=(14, 7))

    # Dark theme
    fig.patch.set_facecolor('#0a0a14')
    ax.set_facecolor('#0a0a14')

    # Plot lines
    ax.plot(hours, opus, color='#ff4444', linewidth=2.5, label='Opus 1M Standalone', alpha=0.9)
    ax.plot(hours, verantyx, color='#00cccc', linewidth=2.5, label='Verantyx (Opus + Sonnet + Spatial Memory)', alpha=0.9)

    # Fill areas
    ax.fill_between(hours, opus, alpha=0.1, color='#ff4444')
    ax.fill_between(hours, verantyx, alpha=0.1, color='#00cccc')

    # Compacting event markers
    for h, label in [(5, 'Compacting #1'), (12, 'Compacting #2'), (20, 'Compacting #3'), (27, 'Compacting #4')]:
        ax.axvline(x=h, color='#ff4444', linestyle=':', alpha=0.3, linewidth=1)
        ax.annotate(label, xy=(h, 12), fontsize=7, color='#ff6666', alpha=0.6, ha='center')

    # Pure-Through reset markers
    for h in [5, 10, 15, 20, 25]:
        ax.axvline(x=h, color='#00cccc', linestyle=':', alpha=0.15, linewidth=1)

    # Measured data point
    ax.scatter([0.5], [82], color='#00ffcc', s=100, zorder=5, edgecolors='white', linewidths=1.5)
    ax.annotate('Measured: 82%\n(Fresh Agent Test)', xy=(0.5, 82), xytext=(3, 92),
                fontsize=9, color='#00ffcc',
                arrowprops=dict(arrowstyle='->', color='#00ffcc', alpha=0.5))

    # Labels and title
    ax.set_xlabel('Session Duration (hours)', fontsize=12, color='white', labelpad=10)
    ax.set_ylabel('Memory Accuracy (%)', fontsize=12, color='white', labelpad=10)
    ax.set_title('Opus 1M Standalone vs Verantyx-Controlled\nMemory Accuracy Over 30-Hour Session',
                 fontsize=16, color='white', fontweight='bold', pad=20)

    # Grid
    ax.grid(True, alpha=0.1, color='white')
    ax.set_xlim(0, 30)
    ax.set_ylim(0, 100)

    # Tick colors
    ax.tick_params(colors='white')
    for spine in ax.spines.values():
        spine.set_color('#333')

    # Legend
    legend = ax.legend(loc='lower left', fontsize=11, facecolor='#1a1a2e', edgecolor='#333',
                      labelcolor='white', framealpha=0.9)

    # Annotations
    ax.annotate('Context pollution\naccumulates', xy=(8, 45), fontsize=9, color='#ff8888',
                style='italic', alpha=0.7, ha='center')
    ax.annotate('Spatial memory\nmaintains accuracy', xy=(15, 88), fontsize=9, color='#66dddd',
                style='italic', alpha=0.7, ha='center')

    # Gap annotation
    mid_h = 15
    mid_opus = opus[int(mid_h * 10)]
    mid_vrx = verantyx[int(mid_h * 10)]
    ax.annotate('', xy=(mid_h, mid_opus), xytext=(mid_h, mid_vrx),
                arrowprops=dict(arrowstyle='<->', color='white', alpha=0.4, linewidth=1.5))
    ax.annotate(f'+{mid_vrx - mid_opus:.0f}%', xy=(mid_h + 0.5, (mid_opus + mid_vrx) / 2),
                fontsize=11, color='white', fontweight='bold', alpha=0.6)

    plt.tight_layout()

    # Save
    output_path = 'docs/benchmark/opus_vs_verantyx.png'
    plt.savefig(output_path, dpi=150, facecolor='#0a0a14', edgecolor='none')
    print(f"✅ Graph saved to {output_path}")

    # Also save SVG
    svg_path = 'docs/benchmark/opus_vs_verantyx.svg'
    plt.savefig(svg_path, facecolor='#0a0a14', edgecolor='none')
    print(f"✅ SVG saved to {svg_path}")

    plt.close()


def generate_ascii_graph(hours, opus, verantyx):
    """Generate ASCII graph as fallback."""
    width = 60
    height = 25

    print("\n  Opus 1M Standalone vs Verantyx — Memory Accuracy (30h)")
    print("  " + "=" * width)

    for y in range(100, -1, -4):
        row = f"  {y:3d}% │"
        for x_idx in range(0, width):
            h = (x_idx / width) * 30
            h_idx = min(int(h * 10), len(hours) - 1)

            o_val = opus[h_idx]
            v_val = verantyx[h_idx]

            o_here = abs(o_val - y) < 2.5
            v_here = abs(v_val - y) < 2.5

            if o_here and v_here:
                row += "X"
            elif v_here:
                row += "●"
            elif o_here:
                row += "○"
            else:
                row += " "

        row += "│"
        print(row)

    print("       └" + "─" * width + "┘")
    print("        0h              10h              20h            30h")
    print()
    print("  ● Verantyx (Opus + Sonnet + Memory)    ○ Opus 1M Standalone")
    print()


def print_data_table(hours, opus, verantyx):
    """Print key data points."""
    print("\n  Key Data Points:")
    print("  ─────────────────────────────────────────────────")
    print(f"  {'Hour':>6}  {'Opus Standalone':>16}  {'Verantyx':>10}  {'Delta':>8}")
    print("  ─────────────────────────────────────────────────")

    for h in [0, 1, 5, 10, 15, 20, 25, 30]:
        idx = min(int(h * 10), len(hours) - 1)
        o = opus[idx]
        v = verantyx[idx]
        d = v - o
        print(f"  {h:5.0f}h  {o:15.1f}%  {v:9.1f}%  {d:+7.1f}%")

    print("  ─────────────────────────────────────────────────")


if __name__ == "__main__":
    hours = np.linspace(0, 30, 301)
    opus = opus_standalone(hours)
    verantyx = verantyx_controlled(hours)

    if HAS_MPL:
        generate_matplotlib_graph(hours, opus, verantyx)
    else:
        print("matplotlib not found. Install with: pip3 install matplotlib")
        generate_ascii_graph(hours, opus, verantyx)

    print_data_table(hours, opus, verantyx)
