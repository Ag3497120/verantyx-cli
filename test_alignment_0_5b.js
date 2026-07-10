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
const path = __importStar(require("path"));
async function runAlignmentTest() {
    console.log("=== Testing Latent Alignment (Puzzle Inference) ===");
    const jgenPath = path.resolve(__dirname, 'qwen_0.5b_full.jgen');
    const engine = new ffi_driver_0_5b_1.JCrossEngineDriver05B(jgenPath);
    // We create a mock thought vector (random but fixed seed equivalent)
    const hiddenDim = 896; // For Qwen 0.5B
    const thoughtVector = new Float32Array(hiddenDim);
    for (let i = 0; i < hiddenDim; i++) {
        thoughtVector[i] = (Math.random() - 0.5) * 0.1;
    }
    console.log("Initial thought vector created.");
    // 1. Check initial entropy before alignment
    const initialRes = engine.executePuzzleInference("lm_head", thoughtVector);
    console.log(`[Before Alignment] Max Token ID: ${initialRes.token}, Entropy: ${initialRes.entropy.toFixed(4)}`);
    // 2. Perform Latent Gradient Descent (Alignment)
    console.log("\nStarting spatial alignment (Gradient Descent)...");
    const finalEntropy = engine.optimizeThoughtInPlace("lm_head", thoughtVector, 50, 100.0, 1.0);
    console.log(`[After Alignment] Final Entropy from rust loop: ${finalEntropy.toFixed(4)}`);
    // 3. Check final entropy and locked token
    const finalRes = engine.executePuzzleInference("lm_head", thoughtVector);
    console.log(`[After Alignment] Max Token ID: ${finalRes.token}, Entropy: ${finalRes.entropy.toFixed(4)}`);
    engine.destroy();
}
runAlignmentTest().catch(console.error);
//# sourceMappingURL=test_alignment_0_5b.js.map