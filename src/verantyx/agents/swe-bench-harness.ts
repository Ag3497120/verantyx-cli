import * as fs from 'fs';
import * as readline from 'readline';
import { JCrossEngineDriver, JCrossTokenizerDriver, initKoffi } from '../memory/ffi-driver';

export interface SWEBenchInstance {
    instance_id: string;
    text: string;
    repo?: string;
    base_commit?: string;
    [key: string]: any;
}

export interface SWEBenchPrediction {
    instance_id: string;
    model_patch: string;
    model_name_or_path: string;
}

export class SWEBenchHarness {
    private worker: JCrossEngineDriver | null = null;
    private coder: JCrossEngineDriver | null = null;
    private tokenizer: JCrossTokenizerDriver | null = null;

    constructor(
        private jgenPath: string,
        private tokenizerPath: string,
        private hiddenDim: number = 4096
    ) {}

    public async initialize() {
        console.log(`[SWE Harness] Initializing FFI with JGEN path: ${this.jgenPath}...`);
        initKoffi(this.jgenPath);

        console.log("[SWE Harness] Loading Tokenizer...");
        this.tokenizer = new JCrossTokenizerDriver(this.tokenizerPath);
        
        console.log("[SWE Harness] Booting Dual-JGEN Engines (Zero-Copy Mmap)...");
        this.worker = new JCrossEngineDriver(this.jgenPath);
        this.coder = new JCrossEngineDriver(this.jgenPath);
    }

    public async evaluate(inputJsonl: string, outputJsonl: string) {
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
            if (!line.trim()) continue;
            
            const instance: SWEBenchInstance = JSON.parse(line);
            console.log(`\nEvaluating instance: ${instance.instance_id}...`);
            
            try {
                const patch = await this.processInstance(instance);
                
                const prediction: SWEBenchPrediction = {
                    instance_id: instance.instance_id,
                    model_patch: patch,
                    model_name_or_path: "verantyx-dual-jgen-9b"
                };
                
                writeStream.write(JSON.stringify(prediction) + '\n');
                console.log(`[+] Successfully generated patch for ${instance.instance_id}`);
            } catch (err) {
                console.error(`[-] Failed to process ${instance.instance_id}:`, err);
                
                // On failure, output an empty patch to not break SWE-bench evaluation scoring
                const fallbackPrediction: SWEBenchPrediction = {
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

    private async processInstance(instance: SWEBenchInstance): Promise<string> {
        // Construct prompt
        const systemPrompt = `<|im_start|>system\nYou are an expert SWE developer. Please resolve the following issue.<|im_end|>\n`;
        const problemText = instance.problem_statement || instance.text || "";
        const userPrompt = `<|im_start|>user\n${problemText}<|im_end|>\n<|im_start|>assistant\n`;
        const promptTokens = this.tokenizer!.encode(systemPrompt + userPrompt);

        console.log(`[Worker] Using encoded prompt (${promptTokens.length} tokens). Extracting intent...`);
        const intentVector = this.worker!.executeWorkerForward(new Uint32Array(promptTokens), this.hiddenDim);
        console.log(`[Coder] Intent Vector Extracted (${this.hiddenDim} dims). Starting Generation...`);

        // Resonance Search (Using the Coder engine)
        const resonance = this.coder!.executePuzzleInference("lm_head", intentVector);
        console.log(`[Coder] Resonance Lock achieved (Token ID: ${resonance.token})`);
        
        let patchOutput = this.tokenizer!.decode(resonance.token);
        const genLength = 2048; // Set to 2048 for real SWE-bench evaluation

        // Generate from the Coder
        const generatedIds = this.coder!.executeGenerationLoop(resonance.token, genLength);
        for (let i = 0; i < generatedIds.length; i++) {
            if (generatedIds[i] !== 0) {
                patchOutput += this.tokenizer!.decode(generatedIds[i]);
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
        } else {
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
    
    private extractPatch(text: string): string {
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

    public destroy() {
        if (this.worker) this.worker.destroy();
        if (this.coder) this.coder.destroy();
        if (this.tokenizer) this.tokenizer.destroy();
    }
}
