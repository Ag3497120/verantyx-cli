import { readFileSync, existsSync, statSync } from "fs";
import { join } from "path";

// MARK: - Blind Gatekeeper (Virtual File System)

interface VFSFileEntry {
  path: string; // Relative path within app
  app: string | string[]; // "all" or ["app_eat", "app_fish"]
  category: string;
  description: string;
}

interface VFSMapping {
  _meta: { description: string; version: string };
  apps: Record<string, string>;
  files: Record<string, VFSFileEntry>;
}

export interface VFSReport {
  id: string;
  description: string;
  category: string;
  totalLines: number;
  imports: string[];
  types: string[];
  functions: string[];
  exists: boolean;
}

export interface VFSListEntry {
  id: string;
  category: string;
  app: string;
  description: string;
}

export interface VFSSearchResult {
  id: string;
  app: string;
  description: string;
  matches: Array<{ line: number; text: string }>;
}

export class Gatekeeper {
  private mapping: VFSMapping;
  private projectRoot: string;

  constructor(mappingPath: string) {
    this.projectRoot = join(mappingPath, "..", "..");
    if (existsSync(mappingPath)) {
      this.mapping = JSON.parse(readFileSync(mappingPath, "utf-8"));
    } else {
      this.mapping = { _meta: { description: "", version: "1.0" }, apps: {}, files: {} };
    }
  }

  // MARK: - List (virtual IDs only, no real paths)

  list(category?: string | null, appFilter?: string | null): VFSListEntry[] {
    const entries: VFSListEntry[] = [];

    for (const [vid, entry] of Object.entries(this.mapping.files)) {
      if (category && entry.category !== category) continue;

      const appScope = entry.app;
      if (appFilter) {
        if (appScope === "all") {
          // OK
        } else if (Array.isArray(appScope) && !appScope.includes(appFilter)) {
          continue;
        } else if (
          typeof appScope === "string" &&
          appScope !== appFilter &&
          appScope !== "all"
        ) {
          continue;
        }
      }

      const appDisplay =
        appScope === "all"
          ? "all"
          : Array.isArray(appScope)
            ? appScope.join(",")
            : appScope;

      entries.push({
        id: vid,
        category: entry.category,
        app: appDisplay,
        description: entry.description,
      });
    }

    return entries.sort((a, b) => a.id.localeCompare(b.id));
  }

  // MARK: - Report (structure analysis, no real paths exposed)

  report(virtualId: string, appId?: string | null): VFSReport | null {
    const entry = this.mapping.files[virtualId];
    if (!entry) return null;

    const realPath = this.resolvePath(virtualId, appId || undefined);
    if (!realPath || !existsSync(realPath)) {
      return {
        id: virtualId,
        description: entry.description,
        category: entry.category,
        totalLines: 0,
        imports: [],
        types: [],
        functions: [],
        exists: false,
      };
    }

    const content = readFileSync(realPath, "utf-8");
    const lines = content.split("\n");

    const imports = [
      ...new Set(
        lines
          .filter((l) => l.startsWith("import "))
          .map((l) => l.replace("import ", "").trim())
      ),
    ];

    const types = (
      content.match(
        /(?:class|struct|enum|protocol)\s+(\w+)/g
      ) || []
    ).map((m) => m.split(/\s+/)[1]);

    const functions = (content.match(/func\s+(\w+)/g) || []).map(
      (m) => m.replace("func ", "")
    );

    return {
      id: virtualId,
      description: entry.description,
      category: entry.category,
      totalLines: lines.length,
      imports,
      types,
      functions: functions.slice(0, 20),
      exists: true,
    };
  }

  // MARK: - Search (returns virtual IDs, no real paths)

  search(
    pattern: string,
    appFilter?: string | null
  ): VFSSearchResult[] {
    const results: VFSSearchResult[] = [];
    const regex = new RegExp(pattern, "i");

    for (const [vid, entry] of Object.entries(this.mapping.files)) {
      const appsToCheck = this.getAppsForEntry(entry, appFilter);

      for (const appId of appsToCheck) {
        const realPath = this.resolvePath(vid, appId);
        if (!realPath || !existsSync(realPath)) continue;

        try {
          const content = readFileSync(realPath, "utf-8");
          const matches: Array<{ line: number; text: string }> = [];

          content.split("\n").forEach((line, i) => {
            if (regex.test(line)) {
              matches.push({ line: i + 1, text: line.trim().slice(0, 100) });
            }
          });

          if (matches.length > 0) {
            results.push({
              id: vid,
              app: appId,
              description: entry.description,
              matches: matches.slice(0, 5),
            });
          }
        } catch {
          // Skip unreadable files
        }
      }
    }

    return results;
  }

  // MARK: - Read (for worker agents only, content returned without path)

  readFile(virtualId: string, appId?: string, maxLines?: number): string | null {
    const realPath = this.resolvePath(virtualId, appId);
    if (!realPath || !existsSync(realPath)) return null;

    const content = readFileSync(realPath, "utf-8");
    if (maxLines) {
      return content.split("\n").slice(0, maxLines).join("\n");
    }
    return content;
  }

  // MARK: - Private (real path resolution — NEVER exposed to commander)

  private resolvePath(virtualId: string, appId?: string): string | null {
    const entry = this.mapping.files[virtualId];
    if (!entry) return null;

    const appScope = entry.app;
    let resolvedApp = appId;

    if (!resolvedApp) {
      if (appScope === "all") {
        resolvedApp = Object.keys(this.mapping.apps)[0];
      } else if (Array.isArray(appScope)) {
        resolvedApp = appScope[0];
      } else {
        resolvedApp = appScope;
      }
    }

    const appRoot = this.mapping.apps[resolvedApp!];
    if (!appRoot) return null;

    return join(this.projectRoot, appRoot, entry.path);
  }

  private getAppsForEntry(
    entry: VFSFileEntry,
    appFilter?: string | null
  ): string[] {
    let apps: string[];

    if (entry.app === "all") {
      apps = Object.keys(this.mapping.apps);
    } else if (Array.isArray(entry.app)) {
      apps = entry.app;
    } else {
      apps = [entry.app];
    }

    if (appFilter) {
      apps = apps.filter((a) => a === appFilter);
    }

    return apps;
  }
}
