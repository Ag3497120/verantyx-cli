// MARK: - SPATIAL_INDEX.jcross Parser

export interface SpatialAxis {
  name: string; // FRONT, NEAR, MID, DEEP, UP, DOWN
  entries: Record<string, string>;
  description: string;
}

export interface SpatialMemoryMap {
  axes: SpatialAxis[];
}

export class SpatialIndex {
  /**
   * Parse a SPATIAL_INDEX.jcross file into a structured map.
   * JCross format uses CROSS { AXIS NAME { key: "value" } } syntax.
   */
  static parse(content: string): SpatialMemoryMap {
    const axes: SpatialAxis[] = [];
    const axisRegex =
      /AXIS\s+(\w+)\s*\{([^}]*)\}/g;

    let match;
    while ((match = axisRegex.exec(content)) !== null) {
      const name = match[1];
      const body = match[2];
      const entries: Record<string, string> = {};
      let description = "";

      // Parse key: "value" pairs
      const pairRegex = /(\w+):\s*"([^"]*)"/g;
      let pairMatch;
      while ((pairMatch = pairRegex.exec(body)) !== null) {
        if (pairMatch[1] === "description") {
          description = pairMatch[2];
        } else {
          entries[pairMatch[1]] = pairMatch[2];
        }
      }

      axes.push({ name, entries, description });
    }

    return { axes };
  }

  /**
   * Generate a SPATIAL_INDEX.jcross string from a structured map.
   */
  static generate(map: SpatialMemoryMap): string {
    const lines: string[] = [
      "# Verantyx Spatial Memory Index",
      `# Generated: ${new Date().toISOString().split("T")[0]}`,
      "# Purpose: Map of all memories. Read this first to navigate the memory space.",
      "",
      "CROSS spatial_memory {",
    ];

    for (const axis of map.axes) {
      lines.push("");
      lines.push(`    AXIS ${axis.name} {`);
      for (const [key, value] of Object.entries(axis.entries)) {
        lines.push(`        ${key}: "${value}",`);
      }
      if (axis.description) {
        lines.push(`        description: "${axis.description}"`);
      }
      lines.push(`    }`);
    }

    lines.push("}");
    lines.push("");

    return lines.join("\n");
  }

  /**
   * Get the navigation guide for fresh agents.
   */
  static getNavigationGuide(): string {
    return [
      "# Navigation Guide for Fresh Agent:",
      '# 0. Read AXIS FRONT session_experience.md FIRST — previous agent\'s testimony',
      "# 1. Read AXIS FRONT active_context.md and design_decisions.md",
      "# 2. If task relates to specific feature → read relevant AXIS NEAR files",
      "# 3. If need to find a file → read AXIS MID *_structure.md for the relevant app",
      "# 4. AXIS UP contains critical cross-cutting facts (always in mind)",
      "# 5. AXIS DEEP and DOWN are rarely needed",
    ].join("\n");
  }
}
