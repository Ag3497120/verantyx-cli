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
const rpc_1 = require("./rpc");
const vscode_1 = require("./vscode");
const path = __importStar(require("path"));
const Module = __importStar(require("module"));
// Create the IPC connection to Swift
const rpc = new rpc_1.RPCClient();
// Create the shimmed vscode API
const vscodeAPI = (0, vscode_1.createVSCodeAPI)(rpc);
// -----------------------------------------------------------------------------
// Magic: Intercept module loading to inject our fake 'vscode' module
// When an extension does `require('vscode')`, they get our shim.
// -----------------------------------------------------------------------------
const originalRequire = Module.prototype.require;
Module.prototype.require = function (request) {
    if (request === 'vscode') {
        return vscodeAPI;
    }
    // Fallback to normal require for everything else
    return originalRequire.apply(this, arguments);
};
// Notify Swift that the Extension Host is ready
rpc.sendNotification('host.ready', { version: '1.0.0' });
// Listen for extension load requests from Swift (VSIXPackageManager)
rpc.onNotification('extension.load', (params) => {
    try {
        const ext = require(params.main);
        if (ext && ext.activate) {
            // Provide a fake context
            const context = { subscriptions: [] };
            ext.activate(context);
            rpc.sendNotification('extension.loaded', { id: params.id, success: true });
        }
    }
    catch (e) {
        rpc.sendNotification('extension.loaded', { id: params.id, success: false, error: e.toString() });
    }
});
// Keep the process alive
setInterval(() => { }, 1000 * 60 * 60);
//# sourceMappingURL=main.js.map