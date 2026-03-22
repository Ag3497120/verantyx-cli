import {
  readFileSync,
  writeFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  renameSync,
  unlinkSync,
  statSync,
} from "fs";
import { join, basename } from "path";

// MARK: - Memory Engine

export type MemoryZone = "front" | "near" | "mid" | "deep";
const ZONES: MemoryZone[] = ["front", "near", "mid", "deep"];

export interface MemoryEntry {
  name: string;
  zone: MemoryZone;
  path: string;
  size: number;
  modified: Date;
  frontmatter?: Record<string, string>;
}

export class MemoryEngine {
  private root: string;

  constructor(root: string) {
    this.root = root;
    this.ensureStructure();
  }

  getRoot(): string {
    return this.root;
  }

  // MARK: - Setup

  private ensureStructure(): void {
    for (const zone of ZONES) {
      const dir = join(this.root, zone);
      if (!existsSync(dir)) {
        mkdirSync(dir, { recursive: true });
      }
    }
  }

  // MARK: - CRUD

  list(zone?: string): MemoryEntry[] {
    const zones = zone ? [zone as MemoryZone] : ZONES;
    const entries: MemoryEntry[] = [];

    for (const z of zones) {
      const dir = join(this.root, z);
      if (!existsSync(dir)) continue;

      for (const file of readdirSync(dir)) {
        if (!file.endsWith(".md")) continue;
        const filePath = join(dir, file);
        const stat = statSync(filePath);

        entries.push({
          name: file.replace(".md", ""),
          zone: z,
          path: filePath,
          size: stat.size,
          modified: stat.mtime,
          frontmatter: this.parseFrontmatter(filePath),
        });
      }
    }

    return entries;
  }

  read(zone: string, name: string): string | null {
    const fileName = name.endsWith(".md") ? name : `${name}.md`;
    const filePath = join(this.root, zone, fileName);
    if (!existsSync(filePath)) return null;
    return readFileSync(filePath, "utf-8");
  }

  write(zone: MemoryZone, name: string, content: string): void {
    const fileName = name.endsWith(".md") ? name : `${name}.md`;
    const filePath = join(this.root, zone, fileName);
    writeFileSync(filePath, content, "utf-8");
  }

  move(name: string, toZone: MemoryZone): boolean {
    // Find the file in any zone
    for (const zone of ZONES) {
      const fileName = name.endsWith(".md") ? name : `${name}.md`;
      const fromPath = join(this.root, zone, fileName);
      if (existsSync(fromPath)) {
        const toPath = join(this.root, toZone, fileName);
        renameSync(fromPath, toPath);
        return true;
      }
    }
    return false;
  }

  delete(name: string): boolean {
    for (const zone of ZONES) {
      const fileName = name.endsWith(".md") ? name : `${name}.md`;
      const filePath = join(this.root, zone, fileName);
      if (existsSync(filePath)) {
        unlinkSync(filePath);
        return true;
      }
    }
    return false;
  }

  // MARK: - Spatial Index

  readSpatialIndex(): string | null {
    const indexPath = join(this.root, "SPATIAL_INDEX.jcross");
    if (!existsSync(indexPath)) return null;
    return readFileSync(indexPath, "utf-8");
  }

  writeSpatialIndex(content: string): void {
    const indexPath = join(this.root, "SPATIAL_INDEX.jcross");
    writeFileSync(indexPath, content, "utf-8");
  }

  // MARK: - Zone Summary

  listZones(): Record<string, number> {
    const result: Record<string, number> = {};
    for (const zone of ZONES) {
      const dir = join(this.root, zone);
      if (!existsSync(dir)) {
        result[zone] = 0;
        continue;
      }
      result[zone] = readdirSync(dir).filter((f) => f.endsWith(".md")).length;
    }
    return result;
  }

  // MARK: - Front Memory Injection

  /**
   * Get all front/ memories concatenated for injection into agent prompts.
   * This is the forced memory injection — every prompt gets this prepended.
   */
  getFrontMemories(): string {
    const frontDir = join(this.root, "front");
    if (!existsSync(frontDir)) return "";

    const files = readdirSync(frontDir)
      .filter((f) => f.endsWith(".md"))
      .sort((a, b) => {
        // session_experience.md first, then active_context, then others
        const priority: Record<string, number> = {
          "session_experience.md": 0,
          "active_context.md": 1,
          "design_decisions.md": 2,
        };
        return (priority[a] ?? 99) - (priority[b] ?? 99);
      });

    const sections: string[] = [];
    for (const file of files) {
      const content = readFileSync(join(frontDir, file), "utf-8");
      sections.push(`--- ${file} ---\n${content}`);
    }

    return sections.join("\n\n");
  }

  // MARK: - Frontmatter Parser

  private parseFrontmatter(
    filePath: string
  ): Record<string, string> | undefined {
    try {
      const content = readFileSync(filePath, "utf-8");
      const match = content.match(/^---\n([\s\S]*?)\n---/);
      if (!match) return undefined;

      const fm: Record<string, string> = {};
      for (const line of match[1].split("\n")) {
        const [key, ...rest] = line.split(":");
        if (key && rest.length) {
          fm[key.trim()] = rest.join(":").trim();
        }
      }
      return fm;
    } catch {
      return undefined;
    }
  }
}
