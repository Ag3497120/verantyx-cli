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
import { join } from "path";
import { MemoryEntry, MemoryZone, ReadMemoryResult } from "./types.js";

const ZONES: MemoryZone[] = ["front", "near", "mid", "deep"];

export class MemoryEngine {
  private root: string;

  constructor(root: string) {
    this.root = root;
    this.ensureStructure();
  }

  getRoot(): string {
    return this.root;
  }

  private ensureStructure(): void {
    for (const zone of ZONES) {
      const dir = join(this.root, zone);
      if (!existsSync(dir)) {
        mkdirSync(dir, { recursive: true });
      }
    }
  }

  // MARK: - MVCC Lock Management

  private acquireLock(filePath: string): string | null {
    const lockPath = `${filePath}.lock`;
    const maxRetries = 5;
    let attempts = 0;

    while (attempts < maxRetries) {
      if (!existsSync(lockPath)) {
        try {
          writeFileSync(lockPath, Date.now().toString(), { flag: "wx" });
          return lockPath;
        } catch {
          // another process won the race
        }
      } else {
        // Break deadlocks older than 10 seconds
        try {
          const stats = statSync(lockPath);
          if (Date.now() - stats.mtimeMs > 10000) {
            unlinkSync(lockPath);
            continue;
          }
        } catch { /* ignore */ }
      }
      
      // Sleep slightly before retry
      const wait = new Date().getTime() + 100;
      while (new Date().getTime() < wait) {} 
      attempts++;
    }
    
    throw new Error(`LOCK_TIMEOUT: Could not acquire lock for ${filePath}`);
  }

  private releaseLock(lockPath: string): void {
    if (existsSync(lockPath)) {
      try {
        unlinkSync(lockPath);
      } catch { /* ignore */ }
    }
  }

  // MARK: - MVCC CRUD Operations

  list(zone?: string): MemoryEntry[] {
    const zones = zone ? [zone as MemoryZone] : ZONES;
    const entries: MemoryEntry[] = [];

    for (const z of zones) {
      const dir = join(this.root, z);
      if (!existsSync(dir)) continue;

      for (const file of readdirSync(dir)) {
        if (!file.endsWith(".md") && !file.endsWith(".jcross")) continue;
        const filePath = join(dir, file);
        const stat = statSync(filePath);

        entries.push({
          name: file.replace(/\.(md|jcross)$/, ""),
          zone: z,
          path: filePath,
          size: stat.size,
          modified: stat.mtime,
          version: stat.mtimeMs,
          frontmatter: this.parseFrontmatter(filePath),
        });
      }
    }

    return entries;
  }

  read(zone: string, name: string): ReadMemoryResult | null {
    const fileName = (name.endsWith(".md") || name.endsWith(".jcross")) ? name : `${name}.md`;
    const filePath = join(this.root, zone, fileName);
    
    if (!existsSync(filePath)) return null;

    const lockPath = this.acquireLock(filePath);
    try {
        const content = readFileSync(filePath, "utf-8");
        const version = statSync(filePath).mtimeMs;
        const frontmatter = this.parseFrontmatter(filePath);
        
        // Touch on read to reset LRU drop
        this.touch(zone as MemoryZone, fileName);
        
        return { content, version, frontmatter };
    } finally {
        if (lockPath) this.releaseLock(lockPath);
    }
  }

  /**
   * Optimistic Concurrency Write
   * @param expectedVersion Supplying this ensures no background agent modified it since we read it.
   */
  write(zone: MemoryZone, name: string, content: string, expectedVersion?: number): void {
    const fileName = (name.endsWith(".md") || name.endsWith(".jcross")) ? name : `${name}.md`;
    const filePath = join(this.root, zone, fileName);
    
    const lockPath = this.acquireLock(filePath);
    try {
        if (existsSync(filePath) && expectedVersion !== undefined) {
            const currentVersion = statSync(filePath).mtimeMs;
            if (currentVersion !== expectedVersion) {
                throw new Error(`STALE_MEMORY: Memory '${name}' was modified by another agent. Expected v${expectedVersion}, got v${currentVersion}`);
            }
        }
        
        writeFileSync(filePath, content, "utf-8");
        // Always bump modify time on write to reset LRU
        const time = new Date();
        import("fs").then(fs => fs.utimesSync(filePath, time, time));
    } finally {
        if (lockPath) this.releaseLock(lockPath);
    }
  }

  /**
   * Updates access time so file stays hot in LRU caches.
   */
  touch(zone: MemoryZone, name: string): void {
      const fileName = (name.endsWith(".md") || name.endsWith(".jcross")) ? name : `${name}.md`;
      const filePath = join(this.root, zone, fileName);
      if (existsSync(filePath)) {
          const time = new Date();
          import("fs").then(fs => fs.utimesSync(filePath, time, time)).catch(() => {});
      }
  }

  /**
   * Scans a zone and returns files that exceed the count limit, starting with the least recently accessed.
   */
  getOverflowCandidates(zone: MemoryZone, limit: number): string[] {
      const dir = join(this.root, zone);
      if (!existsSync(dir)) return [];

      const files = readdirSync(dir).filter(f => f.endsWith(".md") || f.endsWith(".jcross"));
      if (files.length <= limit) return [];

      // Sort by mtimeMs ascending (oldest first)
      const sorted = files.map(file => {
          const filePath = join(dir, file);
          return { name: file, time: statSync(filePath).mtimeMs };
      }).sort((a, b) => a.time - b.time);

      const overflowCount = files.length - limit;
      return sorted.slice(0, overflowCount).map(f => f.name);
  }

  move(name: string, toZone: MemoryZone): boolean {
    for (const zone of ZONES) {
      const fileName = (name.endsWith(".md") || name.endsWith(".jcross")) ? name : `${name}.md`;
      const fromPath = join(this.root, zone, fileName);
      if (existsSync(fromPath)) {
        const toPath = join(this.root, toZone, fileName);
        
        const lockFrom = this.acquireLock(fromPath);
        const lockTo = this.acquireLock(toPath);
        try {
            renameSync(fromPath, toPath);
        } finally {
            if (lockFrom) this.releaseLock(lockFrom);
            if (lockTo) this.releaseLock(lockTo);
        }
        return true;
      }
    }
    return false;
  }

  delete(name: string): boolean {
    for (const zone of ZONES) {
      const fileName = (name.endsWith(".md") || name.endsWith(".jcross")) ? name : `${name}.md`;
      const filePath = join(this.root, zone, fileName);
      if (existsSync(filePath)) {
        const lockPath = this.acquireLock(filePath);
        try {
            unlinkSync(filePath);
        } finally {
            if (lockPath) this.releaseLock(lockPath);
        }
        return true;
      }
    }
    return false;
  }

  readSpatialIndex(): string | null {
    const indexPath = join(this.root, "SPATIAL_INDEX.jcross");
    if (!existsSync(indexPath)) return null;
    return readFileSync(indexPath, "utf-8");
  }

  writeSpatialIndex(content: string): void {
    const indexPath = join(this.root, "SPATIAL_INDEX.jcross");
    writeFileSync(indexPath, content, "utf-8");
  }

  listZones(): Record<string, number> {
    const result: Record<string, number> = {};
    for (const zone of ZONES) {
      const dir = join(this.root, zone);
      if (!existsSync(dir)) {
        result[zone] = 0;
        continue;
      }
      result[zone] = readdirSync(dir).filter((f) => f.endsWith(".md") || f.endsWith(".jcross")).length;
    }
    return result;
  }

  getFrontMemories(): string {
    const frontDir = join(this.root, "front");
    if (!existsSync(frontDir)) return "";

    const files = readdirSync(frontDir)
      .filter((f) => f.endsWith(".md") || f.endsWith(".jcross"))
      .sort((a, b) => {
        const priority: Record<string, number> = {
          "session_experience.md": 0,
          "active_context.md": 1,
          "design_decisions.md": 2,
        };
        return (priority[a] ?? 99) - (priority[b] ?? 99);
      });

    const sections: string[] = [];
    for (const file of files) {
      const filePath = join(frontDir, file);
      // Wait for implicit locks if required, skipping failure if purely reading
      const lockPath = `${filePath}.lock`;
      if (!existsSync(lockPath)) {
          const content = readFileSync(filePath, "utf-8");
          const version = statSync(filePath).mtimeMs;
          sections.push(`--- ${file} (v: ${version}) ---\n${content}`);
      }
    }

    return sections.join("\n\n");
  }

  private parseFrontmatter(filePath: string): Record<string, string> | undefined {
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

