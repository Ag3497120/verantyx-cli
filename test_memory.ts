import { compileTriLayerJCross } from "./src/verantyx/memory/auto-selector.js";
import path from "path";

(async () => {
    const root = path.resolve(process.env.HOME || "~", ".openclaw/memory");
    await compileTriLayerJCross("user message", "assistant message", "main AI intent", root);
    console.log("Finished script.");
})();
