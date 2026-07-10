import { RPCClient } from './rpc';
export declare class OutputChannel {
    readonly name: string;
    private rpc;
    constructor(name: string, rpc: RPCClient);
    append(value: string): void;
    appendLine(value: string): void;
    clear(): void;
    show(preserveFocus?: boolean): void;
    hide(): void;
    dispose(): void;
}
export declare class WindowExt {
    private rpc;
    constructor(rpc: RPCClient);
    createOutputChannel(name: string): OutputChannel;
    showQuickPick(items: string[] | any[], options?: any): Promise<any>;
    showInputBox(options?: any): Promise<string | undefined>;
}
//# sourceMappingURL=window.d.ts.map