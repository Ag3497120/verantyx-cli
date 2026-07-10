"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.FileSystem = void 0;
const rpc_1 = require("./rpc");
const types_1 = require("./types");
class FileSystem {
    rpc;
    constructor(rpc) {
        this.rpc = rpc;
    }
    async stat(uri) {
        return await this.rpc.sendRequest('workspace.fs.stat', { uri: uri.toString() });
    }
    async readDirectory(uri) {
        return await this.rpc.sendRequest('workspace.fs.readDirectory', { uri: uri.toString() });
    }
    async createDirectory(uri) {
        await this.rpc.sendRequest('workspace.fs.createDirectory', { uri: uri.toString() });
    }
    async readFile(uri) {
        const base64 = await this.rpc.sendRequest('workspace.fs.readFile', { uri: uri.toString() });
        return Buffer.from(base64, 'base64');
    }
    async writeFile(uri, content) {
        const base64 = Buffer.from(content).toString('base64');
        await this.rpc.sendRequest('workspace.fs.writeFile', { uri: uri.toString(), content: base64 });
    }
    async delete(uri, options) {
        await this.rpc.sendRequest('workspace.fs.delete', { uri: uri.toString(), options });
    }
    async rename(source, target, options) {
        await this.rpc.sendRequest('workspace.fs.rename', { source: source.toString(), target: target.toString(), options });
    }
}
exports.FileSystem = FileSystem;
//# sourceMappingURL=workspace_fs.js.map