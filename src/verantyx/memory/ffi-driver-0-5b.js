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
exports.JCrossTokenizerDriver = exports.JCrossEngineDriver05B = void 0;
const koffi_1 = require("koffi");
// Standard dynamic import for koffi
const koffi = require('koffi');
const path = __importStar(require("path"));
const os = __importStar(require("os"));
// Resolve library extension based on OS
const ext = os.platform() === 'darwin' ? 'dylib' : os.platform() === 'win32' ? 'dll' : 'so';
const libPath = path.resolve(__dirname, '..', '..', '..', 'jcross_engine_0_5b', 'target', 'release', `libjcross_engine_0_5b.${ext}`);
console.log(`[JCross FFIDriver 0.5B] Loading engine from: ${libPath}`);
const lib = koffi.load(libPath);
// C-FFI Signatures
const jcross_engine_create = lib.func('void* jcross_engine_create(const char *path)');
const jcross_engine_project = lib.func('int jcross_engine_project(void* engine_ptr, const char *layer_name, const float *input_ptr, size_t input_len, float *out_ptr, size_t out_len)');
const jcross_engine_resynthesize = lib.func('int jcross_engine_resynthesize(void* engine_ptr, const char *layer_name, const float *input_ptr, size_t input_len, float temperature, float *out_ptr, size_t out_len)');
const jcross_engine_puzzle_inference = lib.func('int jcross_engine_puzzle_inference(void* engine_ptr, const char *layer_name, const float *input_ptr, size_t input_len, uint32_t *out_token, float *out_entropy)');
const jcross_engine_optimize_thought_in_place = lib.func('int jcross_engine_optimize_thought_in_place(void* engine_ptr, const char *layer_name, float *input_ptr, size_t input_len, size_t max_steps, float lr, float temperature, float *out_entropy)');
const jcross_engine_generate = lib.func('int jcross_engine_generate(void* engine_ptr, uint32_t start_token, size_t max_tokens, uint32_t *out_ptr, size_t out_len)');
const jcross_engine_encode = lib.func('int jcross_engine_encode(void* engine_ptr, const uint32_t *tokens_ptr, size_t tokens_len, float *out_ptr, size_t out_len)');
const jcross_engine_destroy = lib.func('void jcross_engine_destroy(void* engine_ptr)');
const jcross_tokenizer_create = lib.func('void* jcross_tokenizer_create(const char *path)');
const jcross_tokenizer_decode = lib.func('void* jcross_tokenizer_decode(void* tokenizer_ptr, uint32_t token_id)');
const jcross_tokenizer_encode = lib.func('void* jcross_tokenizer_encode(void* tokenizer_ptr, const char *text, size_t *out_len)');
const jcross_tokenizer_free_string = lib.func('void jcross_tokenizer_free_string(void* s)');
const jcross_tokenizer_free_tokens = lib.func('void jcross_tokenizer_free_tokens(void* tokens_ptr, size_t len)');
const jcross_tokenizer_destroy = lib.func('void jcross_tokenizer_destroy(void* tokenizer_ptr)');
class JCrossEngineDriver05B {
    enginePtr = null;
    constructor(jgenPath) {
        console.log(`[JCross FFIDriver] Initializing engine with ${jgenPath}...`);
        this.enginePtr = jcross_engine_create(jgenPath);
        if (!this.enginePtr) {
            console.error("[JCross FFIDriver] Failed to load engine! (File not found or invalid format)");
        }
        else {
            console.log("[JCross FFIDriver] Engine loaded successfully. O(1) Memory Mapping complete.");
        }
    }
    projectSubspace(layerName, inputVector, outputLen) {
        if (!this.enginePtr)
            throw new Error("Engine not initialized");
        const outBuffer = new Float32Array(outputLen);
        console.log(`[JCross FFIDriver] Projecting vector through ${layerName} (Length: ${inputVector.length})`);
        const result = jcross_engine_project(this.enginePtr, layerName, inputVector, inputVector.length, outBuffer, outputLen);
        if (result !== 0) {
            throw new Error(`[JCross FFIDriver] Projection failed with error code: ${result}`);
        }
        return outBuffer;
    }
    resynthesizeVector(layerName, inputVector, outputLen, temperature = 0.1) {
        if (!this.enginePtr)
            throw new Error("Engine not initialized");
        const outBuffer = new Float32Array(outputLen);
        console.log(`[JCross FFIDriver] Resynthesizing vector through ${layerName} (Length: ${inputVector.length}, Temp: ${temperature})`);
        const result = jcross_engine_resynthesize(this.enginePtr, layerName, inputVector, inputVector.length, temperature, outBuffer, outputLen);
        if (result !== 0) {
            throw new Error(`[JCross FFIDriver] Resonance failed with error code: ${result}`);
        }
        return outBuffer;
    }
    executePuzzleInference(layerName, inputVector) {
        if (!this.enginePtr)
            throw new Error("Engine not initialized");
        const outToken = new Uint32Array(1);
        const outEntropy = new Float32Array(1);
        const result = jcross_engine_puzzle_inference(this.enginePtr, layerName, inputVector, inputVector.length, outToken, outEntropy);
        if (result !== 0) {
            throw new Error(`[JCross FFIDriver] Puzzle Inference failed with error code: ${result}`);
        }
        return {
            token: outToken[0],
            entropy: outEntropy[0]
        };
    }
    optimizeThoughtInPlace(layerName, inputVector, maxSteps = 20, lr = 0.01, temperature = 1.0) {
        if (!this.enginePtr)
            throw new Error("Engine not initialized");
        const outEntropy = new Float32Array(1);
        console.log(`[JCross FFIDriver] Optimizing vector (Latent Gradient Descent) on ${layerName} (Length: ${inputVector.length})`);
        const result = jcross_engine_optimize_thought_in_place(this.enginePtr, layerName, inputVector, inputVector.length, maxSteps, lr, temperature, outEntropy);
        if (result !== 0) {
            throw new Error(`[JCross FFIDriver] Vector Optimization failed with error code: ${result}`);
        }
        return outEntropy[0];
    }
    executeGenerationLoop(startToken, maxTokens) {
        if (!this.enginePtr)
            throw new Error("Engine not initialized");
        const outLen = maxTokens + 1; // Start token + generated
        const outPtr = Buffer.alloc(outLen * 4); // 4 bytes per u32
        const result = jcross_engine_generate(this.enginePtr, startToken, maxTokens, outPtr, outLen);
        if (result < 0) {
            throw new Error(`Generation failed with error code: ${result}`);
        }
        const generatedArray = new Uint32Array(result);
        for (let i = 0; i < result; i++) {
            generatedArray[i] = outPtr.readUInt32LE(i * 4);
        }
        return generatedArray;
    }
    executeWorkerForward(tokens, outDim) {
        if (!this.enginePtr)
            throw new Error("Engine not initialized");
        const outPtr = Buffer.alloc(outDim * 4); // 4 bytes per float
        const result = jcross_engine_encode(this.enginePtr, tokens, tokens.length, outPtr, outDim);
        if (result < 0) {
            throw new Error(`Worker forward pass failed with error code: ${result}`);
        }
        const outArray = new Float32Array(outDim);
        for (let i = 0; i < outDim; i++) {
            outArray[i] = outPtr.readFloatLE(i * 4);
        }
        return outArray;
    }
    destroy() {
        if (this.enginePtr) {
            jcross_engine_destroy(this.enginePtr);
            this.enginePtr = null;
        }
    }
}
exports.JCrossEngineDriver05B = JCrossEngineDriver05B;
class JCrossTokenizerDriver {
    tokenizerPtr = null;
    constructor(pathStr) {
        this.tokenizerPtr = jcross_tokenizer_create(pathStr);
        if (!this.tokenizerPtr) {
            throw new Error(`Failed to load tokenizer from ${pathStr}`);
        }
    }
    decode(tokenId) {
        if (!this.tokenizerPtr)
            return "";
        const cstrPtr = jcross_tokenizer_decode(this.tokenizerPtr, tokenId);
        if (!cstrPtr)
            return "";
        const decoded = koffi.decode(cstrPtr, 'char', -1);
        jcross_tokenizer_free_string(cstrPtr);
        return decoded;
    }
    encode(text) {
        if (!this.tokenizerPtr)
            return [];
        const outLenBuf = Buffer.alloc(8); // size_t is 8 bytes on 64-bit
        const ptr = jcross_tokenizer_encode(this.tokenizerPtr, text, outLenBuf);
        if (!ptr)
            return [];
        // Read outLen depending on architecture (size_t)
        const len = Number(outLenBuf.readBigUInt64LE(0));
        const generatedArray = koffi.decode(ptr, 'uint32_t', len);
        const result = Array.from(generatedArray);
        jcross_tokenizer_free_tokens(ptr, len);
        return result;
    }
    destroy() {
        if (this.tokenizerPtr) {
            jcross_tokenizer_destroy(this.tokenizerPtr);
            this.tokenizerPtr = null;
        }
    }
}
exports.JCrossTokenizerDriver = JCrossTokenizerDriver;
//# sourceMappingURL=ffi-driver-0-5b.js.map