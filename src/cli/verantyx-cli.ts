import type { Command } from "commander";
import { MemoryEngine, type MemoryZone } from "../verantyx/memory/engine.js";
import { Gatekeeper } from "../verantyx/vfs/gatekeeper.js";
import { existsSync, readFileSync } from "fs";
import { join } from "path";
import { execSync } from "child_process";

// MARK: - Verantyx Memory CLI

function resolveMemoryRoot(): string {
  return (
    process.env.VERANTYX_MEMORY_ROOT ||
    join(process.env.HOME || "~", ".verantyx", "memory")
  );
}

function resolveVfsMappingPath(): string {
  return (
    process.env.VERANTYX_VFS_MAPPING ||
    join(process.cwd(), ".verantyx", "vfs_mapping.json")
  );
}

export function registerVerantyxMemoryCli(program: Command) {
  const memory = program
    .command("spatial")
    .description("Verantyx spatial memory management");

  memory
    .command("list")
    .description("List memories in spatial layout")
    .option("-z, --zone <zone>", "Filter by zone (front/near/mid/deep)")
    .action((opts: { zone?: string }) => {
      const engine = new MemoryEngine(resolveMemoryRoot());
      const entries = engine.list(opts.zone);

      const zones: Record<string, typeof entries> = {};
      for (const e of entries) {
        if (!zones[e.zone]) zones[e.zone] = [];
        zones[e.zone].push(e);
      }

      for (const [zone, files] of Object.entries(zones)) {
        console.log(`\n  📁 ${zone}/`);
        for (const f of files) {
          const desc = f.frontmatter?.description || "";
          console.log(
            `    📄 ${f.name}${desc ? ` — ${desc.slice(0, 60)}` : ""}`
          );
        }
      }
      console.log();
    });

  memory
    .command("read <name>")
    .description("Read a specific memory")
    .action((name: string) => {
      const engine = new MemoryEngine(resolveMemoryRoot());
      const zones: MemoryZone[] = ["front", "near", "mid", "deep"];
      for (const zone of zones) {
        const content = engine.read(zone, name);
        if (content) {
          console.log(`\n📄 ${zone}/${name}.md\n`);
          console.log(content);
          return;
        }
      }
      console.error(`Memory '${name}' not found`);
    });

  memory
    .command("write <zone> <name>")
    .description("Write a memory to a zone")
    .option("-c, --content <content>", "Memory content")
    .option("-f, --file <file>", "Read content from file")
    .action(
      (zone: string, name: string, opts: { content?: string; file?: string }) => {
        const engine = new MemoryEngine(resolveMemoryRoot());
        let content = opts.content || "";
        if (opts.file) content = readFileSync(opts.file, "utf-8");
        if (!content) {
          console.error("No content provided. Use --content or --file");
          return;
        }
        engine.write(zone as MemoryZone, name, content);
        console.log(`✅ Written to ${zone}/${name}.md`);
      }
    );

  memory
    .command("move <name> <toZone>")
    .description("Move a memory to a different zone")
    .action((name: string, toZone: string) => {
      const engine = new MemoryEngine(resolveMemoryRoot());
      if (engine.move(name, toZone as MemoryZone)) {
        console.log(`✅ Moved '${name}' to ${toZone}/`);
      } else {
        console.error(`Memory '${name}' not found`);
      }
    });

  memory
    .command("index")
    .description("Show SPATIAL_INDEX.jcross")
    .action(() => {
      const engine = new MemoryEngine(resolveMemoryRoot());
      const index = engine.readSpatialIndex();
      if (index) {
        console.log("\n🗺️  SPATIAL_INDEX.jcross\n");
        console.log(index);
      } else {
        console.error("No SPATIAL_INDEX.jcross found");
      }
    });

  memory
    .command("freshness")
    .description("Check memory freshness against git changes")
    .action(() => {
      const engine = new MemoryEngine(resolveMemoryRoot());
      const entries = engine.list("mid");

      console.log("\n🔍 Memory Freshness Check\n");

      for (const entry of entries) {
        const daysSince = Math.floor(
          (Date.now() - entry.modified.getTime()) / (1000 * 60 * 60 * 24)
        );
        let gitChanges = 0;
        try {
          const since = entry.modified.toISOString().split("T")[0];
          const result = execSync(
            `git log --oneline --since="${since}" --all 2>/dev/null | wc -l`,
            { encoding: "utf-8" }
          ).trim();
          gitChanges = parseInt(result) || 0;
        } catch {
          /* not in git repo */
        }

        const status =
          gitChanges === 0
            ? "✅ Fresh"
            : gitChanges < 5
              ? `⚠️  ${gitChanges} commits since update`
              : `❌ Stale (${gitChanges} commits behind)`;

        console.log(`  ${status}  ${entry.name} (${daysSince}d ago)`);
      }
      console.log();
    });

  memory
    .command("inject")
    .description("Show what would be injected into agent prompt (front/ contents)")
    .action(() => {
      const engine = new MemoryEngine(resolveMemoryRoot());
      const front = engine.getFrontMemories();
      if (front) {
        console.log("\n💉 Front Memory Injection Preview\n");
        console.log(front);
        console.log(`\n(${front.length} chars, ~${Math.ceil(front.length / 4)} tokens)\n`);
      } else {
        console.log("No front/ memories to inject");
      }
    });
}

// MARK: - Verantyx VFS CLI

export function registerVerantyxVfsCli(program: Command) {
  const vfs = program
    .command("vfs")
    .description("Verantyx Virtual File System (Blind Gatekeeper)");

  vfs
    .command("list")
    .description("List virtual files")
    .option("-c, --category <category>", "Filter by category")
    .option("-a, --app <app>", "Filter by app ID")
    .action((opts: { category?: string; app?: string }) => {
      const gk = new Gatekeeper(resolveVfsMappingPath());
      const entries = gk.list(opts.category, opts.app);

      console.log(
        `\n${"ID".padEnd(22)} ${"Category".padEnd(14)} ${"App".padEnd(16)} Description`
      );
      console.log("-".repeat(80));

      for (const e of entries) {
        console.log(
          `${e.id.padEnd(22)} ${e.category.padEnd(14)} ${e.app.padEnd(16)} ${e.description}`
        );
      }
      console.log();
    });

  vfs
    .command("report <virtualId>")
    .description("Generate report for a virtual file")
    .option("-a, --app <app>", "App ID")
    .action((virtualId: string, opts: { app?: string }) => {
      const gk = new Gatekeeper(resolveVfsMappingPath());
      const report = gk.report(virtualId, opts.app);

      if (!report) {
        console.error(`Virtual ID '${virtualId}' not found`);
        return;
      }

      console.log(`\n📊 Report: ${report.id}\n`);
      console.log(`  Description: ${report.description}`);
      console.log(`  Category:    ${report.category}`);
      console.log(`  Lines:       ${report.totalLines}`);
      console.log(`  Imports:     ${report.imports.join(", ")}`);
      console.log(`  Types:       ${report.types.join(", ")}`);
      console.log(
        `  Functions:   ${report.functions.slice(0, 10).join(", ")}${
          report.functions.length > 10
            ? ` (+${report.functions.length - 10} more)`
            : ""
        }`
      );
      console.log();
    });

  vfs
    .command("search <pattern>")
    .description("Search across virtual files")
    .option("-a, --app <app>", "Filter by app ID")
    .action((pattern: string, opts: { app?: string }) => {
      const gk = new Gatekeeper(resolveVfsMappingPath());
      const results = gk.search(pattern, opts.app);

      console.log(
        `\n🔍 Search: "${pattern}"${opts.app ? ` in ${opts.app}` : ""}\n`
      );

      if (results.length === 0) {
        console.log("  No matches found");
        return;
      }

      for (const r of results) {
        console.log(`  ${r.id} (${r.app}) — ${r.description}`);
        for (const m of r.matches) {
          console.log(`    L${m.line}: ${m.text}`);
        }
        console.log();
      }
    });
}
