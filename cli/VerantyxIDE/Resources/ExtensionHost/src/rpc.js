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
exports.RPCClient = void 0;
const readline = __importStar(require("readline"));
class RPCClient {
    requestIDCounter = 0;
    pendingRequests = new Map();
    notificationListeners = new Map();
    constructor() {
        const rl = readline.createInterface({
            input: process.stdin,
            output: process.stdout,
            terminal: false
        });
        rl.on('line', (line) => {
            if (!line.trim())
                return;
            try {
                const msg = JSON.parse(line);
                this.handleMessage(msg);
            }
            catch (e) {
                console.error('Failed to parse RPC message:', e);
            }
        });
    }
    handleMessage(msg) {
        if (msg.id !== undefined && (msg.result !== undefined || msg.error !== undefined)) {
            // It's a response
            const resolve = this.pendingRequests.get(msg.id);
            if (resolve) {
                resolve(msg.result);
                this.pendingRequests.delete(msg.id);
            }
        }
        else if (msg.method) {
            // It's a request from Swift
            this.handleRequestFromSwift(msg);
        }
    }
    async handleRequestFromSwift(msg) {
        if (msg.id === undefined) {
            // It's a notification from Swift
            const listener = this.notificationListeners.get(msg.method);
            if (listener) {
                listener(msg.params);
            }
            return;
        }
        // Handle calls from Swift to the extension host (e.g. extension activate request)
        if (msg.method === 'extension.activate') {
            this.sendResponse(msg.id, { success: true });
        }
    }
    onNotification(method, listener) {
        this.notificationListeners.set(method, listener);
    }
    sendNotification(method, params = {}) {
        const payload = JSON.stringify({
            jsonrpc: '2.0',
            method,
            params
        });
        process.stdout.write(payload + '\n');
    }
    sendRequest(method, params = {}) {
        return new Promise((resolve) => {
            const id = this.requestIDCounter++;
            this.pendingRequests.set(id, resolve);
            const payload = JSON.stringify({
                jsonrpc: '2.0',
                id,
                method,
                params
            });
            process.stdout.write(payload + '\n');
        });
    }
    sendResponse(id, result) {
        const payload = JSON.stringify({
            jsonrpc: '2.0',
            id,
            result
        });
        process.stdout.write(payload + '\n');
    }
}
exports.RPCClient = RPCClient;
//# sourceMappingURL=rpc.js.map