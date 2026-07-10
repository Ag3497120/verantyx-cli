import { RPCClient } from './rpc';
import { Disposable } from './types';
export declare class Commands {
    private rpc;
    private localCommands;
    constructor(rpc: RPCClient);
    registerCommand(command: string, callback: (...args: any[]) => any, thisArg?: any): Disposable;
    executeCommand<T>(command: string, ...rest: any[]): Promise<T | undefined>;
}
//# sourceMappingURL=commands.d.ts.map