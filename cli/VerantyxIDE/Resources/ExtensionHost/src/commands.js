"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Commands = void 0;
const rpc_1 = require("./rpc");
const types_1 = require("./types");
class Commands {
    rpc;
    localCommands = new Map();
    constructor(rpc) {
        this.rpc = rpc;
        // Listen for requests from Swift to execute a locally registered command
        this.rpc.onNotification('commands.executeLocalCommand', async (params) => {
            const handler = this.localCommands.get(params.command);
            if (handler) {
                try {
                    const result = await Promise.resolve(handler(...(params.args || [])));
                    this.rpc.sendNotification('commands.executeLocalCommand.response', { requestId: params.requestId, result });
                }
                catch (err) {
                    this.rpc.sendNotification('commands.executeLocalCommand.response', { requestId: params.requestId, error: err.toString() });
                }
            }
            else {
                this.rpc.sendNotification('commands.executeLocalCommand.response', { requestId: params.requestId, error: `Command ${params.command} not found` });
            }
        });
    }
    registerCommand(command, callback, thisArg) {
        const boundCallback = thisArg ? callback.bind(thisArg) : callback;
        this.localCommands.set(command, boundCallback);
        // Notify Swift that this command is available
        this.rpc.sendNotification('commands.registerCommand', { command });
        return new types_1.Disposable(() => {
            this.localCommands.delete(command);
            this.rpc.sendNotification('commands.unregisterCommand', { command });
        });
    }
    async executeCommand(command, ...rest) {
        // If it's a local command, execute it directly
        if (this.localCommands.has(command)) {
            const handler = this.localCommands.get(command);
            return await Promise.resolve(handler(...rest));
        }
        // Otherwise, it might be a built-in VS Code command implemented in Swift
        const result = await this.rpc.sendRequest('commands.executeCommand', { command, args: rest });
        return result;
    }
}
exports.Commands = Commands;
//# sourceMappingURL=commands.js.map