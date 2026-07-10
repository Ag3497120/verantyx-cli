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
exports.SWEBenchHarness05B = void 0;
const fs = __importStar(require("fs"));
const readline = __importStar(require("readline"));
const ffi_driver_0_5b_1 = require("../memory/ffi-driver-0-5b");
class SWEBenchHarness05B {
    jgenPath;
    tokenizerPath;
    hiddenDim;
    worker = null;
    coder = null;
    tokenizer = null;
    constructor(jgenPath, tokenizerPath, hiddenDim = 4096) {
        this.jgenPath = jgenPath;
        this.tokenizerPath = tokenizerPath;
        this.hiddenDim = hiddenDim;
    }
    async initialize() {
        console.log("[SWE Harness] Loading Tokenizer...");
        this.tokenizer = new ffi_driver_0_5b_1.JCrossTokenizerDriver(this.tokenizerPath);
        console.log("[SWE Harness] Booting Dual-JGEN Engines (Zero-Copy Mmap)...");
        this.worker = new ffi_driver_0_5b_1.JCrossEngineDriver05B(this.jgenPath);
        this.coder = new ffi_driver_0_5b_1.JCrossEngineDriver05B(this.jgenPath);
    }
    async evaluate(inputJsonl, outputJsonl) {
        if (!this.worker || !this.coder || !this.tokenizer) {
            throw new Error("Engines not initialized. Call initialize() first.");
        }
        console.log(`[SWE Harness] Starting evaluation on ${inputJsonl}`);
        const fileStream = fs.createReadStream(inputJsonl);
        const rl = readline.createInterface({
            input: fileStream,
            crlfDelay: Infinity
        });
        // Initialize output stream
        const writeStream = fs.createWriteStream(outputJsonl, { flags: 'w' });
        for await (const line of rl) {
            if (!line.trim())
                continue;
            const instance = JSON.parse(line);
            console.log(`\nEvaluating instance: ${instance.instance_id}...`);
            try {
                const patch = await this.processInstance(instance);
                const prediction = {
                    instance_id: instance.instance_id,
                    model_patch: patch,
                    model_name_or_path: "verantyx-dual-jgen-9b"
                };
                writeStream.write(JSON.stringify(prediction) + '\n');
                console.log(`[+] Successfully generated patch for ${instance.instance_id}`);
            }
            catch (err) {
                console.error(`[-] Failed to process ${instance.instance_id}:`, err);
                // On failure, output an empty patch to not break SWE-bench evaluation scoring
                const fallbackPrediction = {
                    instance_id: instance.instance_id,
                    model_patch: "",
                    model_name_or_path: "verantyx-dual-jgen-9b"
                };
                writeStream.write(JSON.stringify(fallbackPrediction) + '\n');
            }
        }
        writeStream.close();
        console.log(`[SWE Harness] Evaluation complete. Results saved to ${outputJsonl}`);
    }
    async processInstance(instance) {
        // Construct prompt
        const systemPrompt = `<|im_start|>system\nYou are an expert SWE developer. Please resolve the following issue.<|im_end|>\n`;
        const problemText = instance.problem_statement || instance.text || "";
        const userPrompt = `<|im_start|>user\n${problemText}<|im_end|>\n<|im_start|>assistant\n`;
        const promptTokens = this.tokenizer.encode(systemPrompt + userPrompt);
        console.log(`[Worker] Using encoded prompt (${promptTokens.length} tokens). Extracting intent...`);
        const intentVector = this.worker.executeWorkerForward(new Uint32Array(promptTokens), this.hiddenDim);
        console.log(`[Coder] Intent Vector Extracted (${intentVector.length} dims). Starting Generation...`);
        // 1. Align the intent vector with the coder's spatial dictionary (True Puzzle Inference)
        console.log(`[Coder] Optimizing thought vector (Latent Gradient Descent)...`);
        const finalEntropy = this.coder.optimizeThoughtInPlace("lm_head", intentVector, 50, 100.0, 1.0);
        console.log(`[Coder] Spatial alignment complete. Entropy lowered to: ${finalEntropy.toFixed(4)}`);
        // 2. Lock the token
        const res = this.coder.executePuzzleInference("lm_head", intentVector);
        console.log(`[Coder] Resonance Lock achieved (Token ID: ${res.token}, Entropy: ${res.entropy.toFixed(4)})`);
        let patchOutput = this.tokenizer.decode(res.token);
        const genLength = 2048; // Set to 2048 for real SWE-bench evaluation
        const generatedIds = this.coder.executeGenerationLoop(res.token, genLength);
        for (let i = 0; i < generatedIds.length; i++) {
            if (generatedIds[i] !== 0) {
                patchOutput += this.tokenizer.decode(generatedIds[i]);
            }
        }
        // Dynamic Adjustment: Find the end of the markdown code block containing the patch.
        // SWE-bench uses diff blocks. The model outputs "```diff\n...\n```"
        const patchStart = patchOutput.indexOf("```diff");
        if (patchStart !== -1) {
            const patchEnd = patchOutput.indexOf("```", patchStart + 7);
            if (patchEnd !== -1) {
                patchOutput = patchOutput.substring(patchStart, patchEnd + 3);
            }
        }
        else {
            // Fallback: If no ```diff block is found, try finding the first generic ``` block
            const genericStart = patchOutput.indexOf("```");
            if (genericStart !== -1) {
                const genericEnd = patchOutput.indexOf("```", genericStart + 3);
                if (genericEnd !== -1) {
                    patchOutput = patchOutput.substring(genericStart, genericEnd + 3);
                }
            }
        }
        return patchOutput;
    }
    extractPatch(text) {
        // If the generation actually produced a diff, try to extract it
        const diffRegex = /```diff\n([\s\S]*?)\n```/;
        const match = text.match(diffRegex);
        if (match && match[1]) {
            return match[1];
        }
        // Fallback: assume the whole text is a patch (since currently it's dummy generation)
        // For POC, we'll return a mock patch format so SWE-bench runner can parse it as a valid patch
        return `--- a/dummy.py\n+++ b/dummy.py\n@@ -1,1 +1,1 @@\n-old\n+new\n# Real output was: ${text.substring(0, 50)}...`;
    }
    destroy() {
        if (this.worker)
            this.worker.destroy();
        if (this.coder)
            this.coder.destroy();
        if (this.tokenizer)
            this.tokenizer.destroy();
    }
}
exports.SWEBenchHarness05B = SWEBenchHarness05B;
//# sourceMappingURL=swe-bench-harness-0-5b.js.map