import type { Command } from "commander";
import { MemoryEngine } from "../verantyx/memory/engine.js";
import type { MemoryZone } from "../verantyx/memory/types.js";
import { Gatekeeper } from "../verantyx/vfs/gatekeeper.js";
import { existsSync, readFileSync } from "fs";
import { join } from "path";
import { execSync } from "child_process";

// MARK: - Verantyx Memory CLI

function resolveMemoryRoot(): string {
  return (
    process.env.RONIN_MEMORY_ROOT ||
    join(process.env.HOME || "~", ".ronin", "memory")
  );
}

function resolveVfsMappingPath(): string {
  return (
    process.env.RONIN_VFS_MAPPING ||
    join(process.cwd(), ".ronin", "vfs_mapping.json")
  );
}

export function registerRoninMemoryCli(program: Command) {
  const memory = program
    .command("spatial")
    .description("Ronin spatial memory management");

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

export function registerRoninVfsCli(program: Command) {
  const vfs = program
    .command("vfs")
    .description("Ronin Virtual File System (Blind Gatekeeper)");

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

// MARK: - Verantyx Local LLM CLI

import { runCalibrationTrials } from "../verantyx/locallm/calibrate.js";
import { runRoninSetup } from "../verantyx/cli/setup/wizard.js";

import { exec, execFile } from "child_process";
import { loadConfig } from "../verantyx/config.js";

export function registerRoninSetupCli(program: Command) {
  program
    .command("setup")
    .description("Interactive setup wizard for Ronin (Language, Fallback Mode)")
    .action(async () => {
      await runRoninSetup();
    });

  program
    .command("start")
    .description("Run setup and boot background services (Local LLM & Browser)")
    .action(async () => {
      await runRoninSetup();
      
      const config = loadConfig();
      const isJa = config.agents.systemLanguage === "ja";
      
      console.log(isJa ? `\n🚀 [Ronin] バックグラウンドサービスを起動中...` : `\n🚀 [Ronin] Booting background services...`);
      
      if (config.agents.cloudFallbackMode === "browser_hitl") {
          console.log(isJa ? `  └─ [Browser] ステルスブラウザを準備しています (Lazy Load)` : `  └─ [Browser] Preparing stealth browser (Lazy Load)`);
      } else {
          console.log(isJa ? `  └─ [Cloud] APIモードが有効です。` : `  └─ [Cloud] API mode is active.`);
      }
      
      // Local LLM Process Start logic
      console.log(isJa ? `  └─ [Local LLM] Ollamaサービスを確認/起動しています...` : `  └─ [Local LLM] Checking/starting Ollama service...`);
      
      exec("ollama serve", (error) => {
          // If ollama is already running it will error out or just exit, which is fine.
      });

      console.log(isJa ? `  └─ [Brain] Qwen-0.5B 潜在メモリデーモンをバックグラウンド起動しています...` : `  └─ [Brain] Starting Qwen-0.5B Latent Memory Daemon...`);
      try {
          const { spawn } = require("child_process");
          const path = require("path");
          const root = process.cwd().endsWith("cortex") ? path.join(process.cwd(), "..") : process.cwd();
          const scriptPath = path.join(root, "cli", "scripts", "qwen_daemon.py");
          
          const child = spawn("python3", [scriptPath], {
              detached: true,
              stdio: "ignore"
          });
          child.unref();
      } catch (e) {}
      
      // Wait a moment for boot text
      await new Promise(r => setTimeout(r, 2000));
      
      console.log(isJa 
        ? `\n✅ 準備完了！ 'ronin vchat' を実行して司令部(Commander)にアクセスしてください。` 
        : `\n✅ Ready! Run 'ronin vchat' to access the Commander.`);
      process.exit(0);
    });
}

export function registerRoninLocallmCli(program: Command) {
  const locallm = program
    .command("locallm")
    .description("Configuration and calibration for Local LLM Agent loops");

  locallm
    .command("calibrate")
    .description("Run the 5 Trials to evaluate the local model's autonomous capabilities")
    .option("-m, --model <model>", "Model name (e.g. gemma:27b, llama3:8b)", "gemma:27b")
    .action(async (opts: { model: string }) => {
      try {
        const result = await runCalibrationTrials(opts.model);
        console.log(`\n=========================================`);
        console.log(`🏆 CALIBRATION COMPLETE`);
        console.log(`   Model: ${opts.model}`);
        console.log(`   Score: ${result.score}/100`);
        console.log(`   Tier:  ${result.tier}`);
        console.log(`\n📝 Gemini 3 Flash Examiner Report:`);
        console.log(`   "${result.report}"`);
        console.log(`=========================================\n`);
      } catch (err: any) {
        console.error(`Calibration failed: ${err.message}`);
      }
    });
}

// MARK: - Verantyx IDE CLI

export function registerVerantyxIdeCli(program: Command) {
  const ide = program
    .command("ide")
    .description("Control the Verantyx Swift IDE directly from CLI");

  const config = ide.command("config").description("Modify IDE configurations");

  config
    .command("set <key> <value>")
    .description("Set an IDE configuration (e.g. exo.role master)")
    .action((key: string, value: string) => {
      try {
        if (key === "exo.role") {
          let role = value.toLowerCase();
          role = role.charAt(0).toUpperCase() + role.slice(1); // "Master", "Worker", "Idle"
          execSync(`defaults write com.verantyx.ide exo_role '"${role}"'`);
          console.log(`✅ [IDE] Set exo.role to ${role}`);
        } else if (key === "exo.enabled") {
          const isEnabled = value.toLowerCase() === "true" || value === "1";
          execSync(`defaults write com.verantyx.ide exo_enabled -bool ${isEnabled}`);
          console.log(`✅ [IDE] Set exo.enabled to ${isEnabled}`);
        } else {
          console.error(`Unknown key: ${key}`);
        }
      } catch (err: any) {
        console.error(`Failed to update IDE settings: ${err.message}`);
      }
    });

  ide
    .command("setup <component>")
    .description("Trigger IDE setup wizards (e.g. exo)")
    .action((component: string) => {
      if (component === "exo") {
        // Trigger setup by setting a special defaults key or just notifying user
        // The swift app could observe "trigger_setup"
        execSync(`defaults write com.verantyx.ide trigger_setup '"exo"'`);
        console.log("✅ [IDE] Triggered Exo setup wizard in Verantyx IDE.");
      } else {
        console.error(`Unknown setup component: ${component}`);
      }
    });
}
