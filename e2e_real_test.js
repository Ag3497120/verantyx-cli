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
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
async function run() {
    console.log("=== Verantyx E2E Pipeline Vector Generation ===");
    const jgenPath = path.resolve(__dirname, 'qwen_9b_full.jgen');
    const driver = new ffi_driver_1.JCrossEngineDriver(jgenPath);
    // Using 3584 dimensions as Qwen-9B uses a hidden_size of 3584
    const realInput = new Float32Array(3584);
    for (let i = 0; i < 3584; i++) {
        realInput[i] = Math.sin(i * 0.01) * 0.5;
    }
    // Since we don't have up_proj generating exactly 3584 for this E2E test, we pass the realInput directly,
    // which simulates a vector successfully projected down into the 3584 manifold space by the JCross rust engine.
    fs.writeFileSync("intent_real.json", JSON.stringify({ vector: Array.from(realInput) }));
    console.log("[E2E] Simulated JCross output vector saved to intent_real.json (3584 dims).");
    driver.destroy();
}
run();
//# sourceMappingURL=e2e_real_test.js.map