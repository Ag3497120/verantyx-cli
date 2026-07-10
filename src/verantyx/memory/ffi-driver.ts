import { Koffi } from 'koffi';
// Standard dynamic import for koffi
const koffi = require('koffi');
import * as path from 'path';
import * as os from 'os';

// Resolve library extension based on OS
const ext = os.platform() === 'darwin' ? 'dylib' : os.platform() === 'win32' ? 'dll' : 'so';
let defaultLibPath = path.resolve(__dirname, '..', '..', '..', 'jcross_engine', 'target', 'release', `libjcross_engine.${ext}`);

// C-FFI Signatures (we load the library lazily inside the class now to allow path injection)
let lib: any = null;
let jcross_engine_create: any, jcross_engine_project: any, jcross_engine_resynthesize: any;
let jcross_engine_puzzle_inference: any, jcross_engine_generate: any, jcross_engine_encode: any, jcross_engine_destroy: any;
let jcross_tokenizer_create: any, jcross_tokenizer_decode: any, jcross_tokenizer_encode: any;
let jcross_tokenizer_free_string: any, jcross_tokenizer_free_tokens: any, jcross_tokenizer_destroy: any;

export function initKoffi(jgenPath: string) {
    if (lib) return; // Already initialized
    let engineLibPath = defaultLibPath;
    if (jgenPath.includes("glm") || jgenPath.includes("qwen") || jgenPath.includes("ornith") || jgenPath.includes("0.5b")) {
        engineLibPath = path.resolve(__dirname, '..', '..', '..', 'jcross_engine_glm', 'target', 'release', `libjcross_engine_glm.${ext}`);
    }
    console.log(`[JCross FFIDriver] Loading engine from: ${engineLibPath}`);
    lib = koffi.load(engineLibPath);
    
    jcross_engine_create = lib.func('void* jcross_engine_create(const char *path)');
    jcross_engine_project = lib.func('int jcross_engine_project(void* engine_ptr, const char *layer_name, const float *input_ptr, size_t input_len, float *out_ptr, size_t out_len)');
    jcross_engine_resynthesize = lib.func('int jcross_engine_resynthesize(void* engine_ptr, const char *layer_name, const float *input_ptr, size_t input_len, float temperature, float *out_ptr, size_t out_len)');
    jcross_engine_puzzle_inference = lib.func('int jcross_engine_puzzle_inference(void* engine_ptr, const char *layer_name, const float *input_ptr, size_t input_len, uint32_t *out_token, float *out_entropy)');
    jcross_engine_generate = lib.func('int jcross_engine_generate(void* engine_ptr, const uint32_t *prompt_ptr, size_t prompt_len, size_t max_tokens, uint32_t *out_ptr, size_t out_len)');
    jcross_engine_encode = lib.func('int jcross_engine_encode(void* engine_ptr, const uint32_t *tokens_ptr, size_t tokens_len, float *out_ptr, size_t out_len)');
    jcross_engine_destroy = lib.func('void jcross_engine_destroy(void* engine_ptr)');

    jcross_tokenizer_create = lib.func('void* jcross_tokenizer_create(const char *path)');
    jcross_tokenizer_decode = lib.func('void* jcross_tokenizer_decode(void* tokenizer_ptr, uint32_t token_id)');
    jcross_tokenizer_encode = lib.func('void* jcross_tokenizer_encode(void* tokenizer_ptr, const char *text, size_t *out_len)');
    jcross_tokenizer_free_string = lib.func('void jcross_tokenizer_free_string(void* s)');
    jcross_tokenizer_free_tokens = lib.func('void jcross_tokenizer_free_tokens(void* tokens_ptr, size_t len)');
    jcross_tokenizer_destroy = lib.func('void jcross_tokenizer_destroy(void* tokenizer_ptr)');
}

export class JCrossEngineDriver {
    private enginePtr: any = null;

    constructor(jgenPath: string) {
        console.log(`[JCross FFIDriver] Initializing engine with ${jgenPath}...`);
        this.enginePtr = jcross_engine_create(jgenPath);
        if (!this.enginePtr) {
            console.error("[JCross FFIDriver] Failed to load engine! (File not found or invalid format)");
        } else {
            console.log("[JCross FFIDriver] Engine loaded successfully. O(1) Memory Mapping complete.");
        }
    }

    public projectSubspace(layerName: string, inputVector: Float32Array, outputLen: number): Float32Array {
        if (!this.enginePtr) throw new Error("Engine not initialized");

        const outBuffer = new Float32Array(outputLen);
        
        console.log(`[JCross FFIDriver] Projecting vector through ${layerName} (Length: ${inputVector.length})`);
        
        const result = jcross_engine_project(
            this.enginePtr,
            layerName,
            inputVector,
            inputVector.length,
            outBuffer,
            outputLen
        );

        if (result !== 0) {
            throw new Error(`[JCross FFIDriver] Projection failed with error code: ${result}`);
        }

        return outBuffer;
    }

    public resynthesizeVector(layerName: string, inputVector: Float32Array, outputLen: number, temperature: number = 0.1): Float32Array {
        if (!this.enginePtr) throw new Error("Engine not initialized");

        const outBuffer = new Float32Array(outputLen);
        
        console.log(`[JCross FFIDriver] Resynthesizing vector through ${layerName} (Length: ${inputVector.length}, Temp: ${temperature})`);
        
        const result = jcross_engine_resynthesize(
            this.enginePtr,
            layerName,
            inputVector,
            inputVector.length,
            temperature,
            outBuffer,
            outputLen
        );

        if (result !== 0) {
            throw new Error(`[JCross FFIDriver] Resonance failed with error code: ${result}`);
        }

        return outBuffer;
    }

    public executePuzzleInference(layerName: string, inputVector: Float32Array): { token: number, entropy: number } {
        if (!this.enginePtr) throw new Error("Engine not initialized");

        const outToken = new Uint32Array(1);
        const outEntropy = new Float32Array(1);
        
        console.log(`[JCross FFIDriver] Executing Latent Resonance Search on ${layerName} (Length: ${inputVector.length})`);
        
        const result = jcross_engine_puzzle_inference(
            this.enginePtr,
            layerName,
            inputVector,
            inputVector.length,
            outToken,
            outEntropy
        );

        if (result !== 0) {
            throw new Error(`[JCross FFIDriver] Puzzle Inference failed with error code: ${result}`);
        }

        return {
            token: outToken[0],
            entropy: outEntropy[0]
        };
    }

    public executeGenerationLoop(promptTokens: Uint32Array, maxTokens: number): Uint32Array {
        if (!this.enginePtr) throw new Error("Engine not initialized");

        const outLen = promptTokens.length + maxTokens + 1;
        const outPtr = Buffer.alloc(outLen * 4); // 4 bytes per u32

        const result = jcross_engine_generate(
            this.enginePtr,
            promptTokens,
            promptTokens.length,
            maxTokens,
            outPtr,
            outLen
        );

        if (result < 0) {
            throw new Error(`Generation failed with error code: ${result}`);
        }

        const generatedArray = new Uint32Array(result);
        for (let i = 0; i < result; i++) {
            generatedArray[i] = outPtr.readUInt32LE(i * 4);
        }

        return generatedArray;
    }

    public executeWorkerForward(tokens: Uint32Array, outDim: number): Float32Array {
        if (!this.enginePtr) throw new Error("Engine not initialized");

        const outPtr = Buffer.alloc(outDim * 4); // 4 bytes per float

        const result = jcross_engine_encode(
            this.enginePtr,
            tokens,
            tokens.length,
            outPtr,
            outDim
        );

        if (result < 0) {
            throw new Error(`Worker forward pass failed with error code: ${result}`);
        }

        const outArray = new Float32Array(outDim);
        for (let i = 0; i < outDim; i++) {
            outArray[i] = outPtr.readFloatLE(i * 4);
        }

        return outArray;
    }

    public destroy() {
        if (this.enginePtr) {
            jcross_engine_destroy(this.enginePtr);
            this.enginePtr = null;
        }
    }
}

export class JCrossTokenizerDriver {
    private tokenizerPtr: any = null;

    constructor(pathStr: string) {
        this.tokenizerPtr = jcross_tokenizer_create(pathStr);
        if (!this.tokenizerPtr) {
            throw new Error(`Failed to load tokenizer from ${pathStr}`);
        }
    }

    public decode(tokenId: number): string {
        if (!this.tokenizerPtr) return "";
        const cstrPtr = jcross_tokenizer_decode(this.tokenizerPtr, tokenId);
        if (!cstrPtr) return "";
        
        const decoded = koffi.decode(cstrPtr, 'char', -1);
        jcross_tokenizer_free_string(cstrPtr);
        return decoded;
    }

    public encode(text: string): number[] {
        if (!this.tokenizerPtr) return [];
        
        const outLenBuf = Buffer.alloc(8); // size_t is 8 bytes on 64-bit
        const ptr = jcross_tokenizer_encode(this.tokenizerPtr, text, outLenBuf);
        if (!ptr) return [];
        
        // Read outLen depending on architecture (size_t)
        const len = Number(outLenBuf.readBigUInt64LE(0));
        const generatedArray = koffi.decode(ptr, 'uint32_t', len);
        const result = Array.from(generatedArray) as number[];
        
        jcross_tokenizer_free_tokens(ptr, len);
        return result;
    }

    public destroy() {
        if (this.tokenizerPtr) {
            jcross_tokenizer_destroy(this.tokenizerPtr);
            this.tokenizerPtr = null;
        }
    }
}
