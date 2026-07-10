"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
const ffi_driver_0_5b_1 = require("./src/verantyx/memory/ffi-driver-0-5b");
const ffi_driver_0_5b_2 = require("./src/verantyx/memory/ffi-driver-0-5b");
const path = __importStar(require("path"));
const fs = __importStar(require("fs"));
async function runPoC() {
    console.log("=== Verantyx Latent Translation PoC ===");
    const jgenPath = path.resolve(__dirname, 'qwen_0.5b_full.jgen');
    if (!fs.existsSync(jgenPath)) {
        console.error("qwen_0.5b_full.jgen not found.");
        return;
    }
    console.log("[System] Booting Worker (Thinking Engine) - O(1) Memory Map...");
    const worker = new ffi_driver_0_5b_1.JCrossEngineDriver05B(jgenPath);
    console.log("[System] Booting Coder (Translation Engine) - O(1) Memory Map...");
    const coder = new ffi_driver_0_5b_1.JCrossEngineDriver05B(jgenPath);
    const tokenizer = new ffi_driver_0_5b_2.JCrossTokenizerDriver(path.resolve(__dirname, 'tokenizer.json'));
    const promptText = "Translate the following intent into a Python script: loop 5 times and print 'Verantyx is awesome'";
    console.log(`\n[User Prompt]: ${promptText}`);
    // 1. Thinking Phase (Worker)
    const promptTokens = tokenizer.encode(promptText);
    console.log(`\n[Worker] Thinking Phase... (Encoding ${promptTokens.length} tokens into pure latent vector)`);
    const hiddenDim = 896;
    // Worker processes the prompt and extracts the core intent vector
    const hWorker = worker.executeWorkerForward(new Uint32Array(promptTokens), hiddenDim);
    console.log(`[Worker] Intent Vector Extracted. Dim: ${hWorker.length}`);
    // 2. Spatial Translation Phase (The Synapse M)
    console.log(`\n[Translation] Applying Latent Translation Matrix M (Identity mapping for this PoC)...`);
    const hCoder = new Float32Array(hWorker); // h_coder = M * h_worker
    // 3. Translation Phase (Coder)
    console.log(`\n[Coder] Translation Phase...`);
    console.log(`[Coder] Optimizing thought vector (Latent Gradient Descent) to align with Coder syntax space...`);
    const finalEntropy = coder.optimizeThoughtInPlace("lm_head", hCoder, 50, 100.0, 1.0);
    console.log(`[Coder] Spatial alignment complete. Entropy locked to: ${finalEntropy.toFixed(4)}`);
    // Lock the first token
    const res = coder.executePuzzleInference("lm_head", hCoder);
    console.log(`[Coder] Resonance Lock achieved. First Token ID: ${res.token}`);
    // Translate the thought structure into Python code
    let patchOutput = tokenizer.decode(res.token);
    console.log(`\n[Coder] Translating Thought into Text (Code):`);
    process.stdout.write(patchOutput);
    const generatedIds = coder.executeGenerationLoop(res.token, 50); // generate 50 tokens
    for (let i = 0; i < generatedIds.length; i++) {
        if (generatedIds[i] !== 0) {
            const word = tokenizer.decode(generatedIds[i]);
            process.stdout.write(word);
        }
        else {
            break; // EOS
        }
    }
    console.log("\n\n=== PoC Complete ===");
    worker.destroy();
    coder.destroy();
}
runPoC();
//# sourceMappingURL=poc_svd_translation.js.map