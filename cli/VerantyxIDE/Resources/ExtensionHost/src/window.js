"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.WindowExt = exports.OutputChannel = void 0;
const rpc_1 = require("./rpc");
const vscode_1 = require("./vscode"); // Assuming WebviewPanel is still exported from vscode.ts or we'll move it
const types_1 = require("./types");
class OutputChannel {
    name;
    rpc;
    constructor(name, rpc) {
        this.name = name;
        this.rpc = rpc;
        this.rpc.sendNotification('window.createOutputChannel', { name });
    }
    append(value) {
        this.rpc.sendNotification('window.outputChannel.append', { name: this.name, value });
    }
    appendLine(value) {
        this.rpc.sendNotification('window.outputChannel.appendLine', { name: this.name, value });
    }
    clear() {
        this.rpc.sendNotification('window.outputChannel.clear', { name: this.name });
    }
    show(preserveFocus) {
        this.rpc.sendNotification('window.outputChannel.show', { name: this.name, preserveFocus });
    }
    hide() {
        this.rpc.sendNotification('window.outputChannel.hide', { name: this.name });
    }
    dispose() {
        this.rpc.sendNotification('window.outputChannel.dispose', { name: this.name });
    }
}
exports.OutputChannel = OutputChannel;
class WindowExt {
    rpc;
    constructor(rpc) {
        this.rpc = rpc;
    }
    createOutputChannel(name) {
        return new OutputChannel(name, this.rpc);
    }
    async showQuickPick(items, options) {
        return await this.rpc.sendRequest('window.showQuickPick', { items, options });
    }
    async showInputBox(options) {
        return await this.rpc.sendRequest('window.showInputBox', { options });
    }
}
exports.WindowExt = WindowExt;
//# sourceMappingURL=window.js.map