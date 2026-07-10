const koffi = require('koffi');
const fs = require('fs');
const path = require('path');
const os = require('os');

const ext = os.platform() === 'darwin' ? 'dylib' : os.platform() === 'win32' ? 'dll' : 'so';
// 改造した jcross_engine_glm のパスを指定
const engineLibPath = path.resolve(__dirname, 'jcross_engine_glm', 'target', 'release', `libjcross_engine_glm.${ext}`);

console.log(`[JCross FFIDriver] Loading engine from: ${engineLibPath}`);
const lib = koffi.load(engineLibPath);

const jcross_engine_create = lib.func('void* jcross_engine_create(const char *path)');
const jcross_engine_project = lib.func('int jcross_engine_project(void* engine_ptr, const char *layer_name, const float *input_ptr, size_t input_len, float *out_ptr, size_t out_len)');
const jcross_engine_destroy = lib.func('void jcross_engine_destroy(void* engine_ptr)');

class JCrossEngineDriver {
    constructor(jgenPath) {
        console.log(`[JCross FFIDriver] Initializing engine with ${jgenPath}...`);
        this.enginePtr = jcross_engine_create(jgenPath);
        if (!this.enginePtr) {
            throw new Error("[JCross FFIDriver] Failed to load engine! (File not found or invalid format)");
        }
        console.log("[JCross FFIDriver] Engine loaded successfully. O(1) Memory Mapping complete.");
    }

    projectSubspace(layerName, inputVector, outputLen) {
        if (!this.enginePtr) throw new Error("Engine not initialized");
        const outBuffer = new Float32Array(outputLen);
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

    destroy() {
        if (this.enginePtr) {
            jcross_engine_destroy(this.enginePtr);
            this.enginePtr = null;
        }
    }
}

async function run() {
    console.log("=== Verantyx Native Engine Boot Test (JS-Inline) ===");
    
    const jgenPath = '/Users/motonishikoudai/Verantyx-God-Mode-Space/cli/qwen_0.5b_full.jgen';
    if (!fs.existsSync(jgenPath)) {
        console.error(`[Test] Error: ${jgenPath} not found.`);
        return;
    }

    try {
        const driver = new JCrossEngineDriver(jgenPath);

        // Dummy vector simulating a Qwen 0.5B embedding (1024 hidden size)
        const dummyInput = new Float32Array(1024);
        dummyInput.fill(0.1);

        console.log("[Test] Executing SVD projection on layer: model.layers.0.mlp.gate_proj.weight");
        
        // Output len is typically intermediate_size (2816) for gate_proj
        const outputBuffer = driver.projectSubspace("model.layers.0.mlp.gate_proj.weight", dummyInput, 2816);
        
        console.log(`[Test] Projection successful! First 5 values: ${outputBuffer.slice(0, 5)}`);

        driver.destroy();
        console.log("=== Test Complete ===");
    } catch (e) {
        console.error("Test failed:", e);
    }
}

run();