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
const ffi_driver_1 = require("./src/verantyx/memory/ffi-driver");
const path = __importStar(require("path"));
async function runDualJgen() {
    console.log("=== Verantyx Dual-JGEN Telepathy Protocol ===");
    const jgenPath = path.resolve(__dirname, 'qwen_9b_full.jgen');
    const coder = new ffi_driver_1.JCrossEngineDriver(jgenPath);
    const intentVector = new Float32Array(4096);
    for (let i = 0; i < 4096; i++)
        intentVector[i] = Math.sin(i * 0.05) * 0.2;
    try {
        const resonance = coder.executePuzzleInference("lm_head.weight", intentVector);
        console.log(`[Coder] Resonance Lock achieved!`);
        console.log(`[Coder] Locked Token ID: ${resonance.token}`);
        console.log(`[Coder] Shannon Entropy (Resistance): ${resonance.entropy.toFixed(4)}`);
    }
    catch (e) {
        console.error("Coder inference failed:", e);
    }
    coder.destroy();
}
runDualJgen();
//# sourceMappingURL=dual_jgen_test.js.map