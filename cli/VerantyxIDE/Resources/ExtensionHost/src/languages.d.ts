import { RPCClient } from './rpc';
import { Disposable } from './types';
import { TextDocument } from './vscode';
export declare class Languages {
    private getDocument;
    private rpc;
    private providers;
    private providerIdCounter;
    constructor(rpc: RPCClient, getDocument: (uri: string) => TextDocument | undefined);
    registerCompletionItemProvider(selector: any, provider: any, ...triggerCharacters: string[]): Disposable;
    registerHoverProvider(selector: any, provider: any): Disposable;
    registerDefinitionProvider(selector: any, provider: any): Disposable;
    private registerProvider;
}
//# sourceMappingURL=languages.d.ts.map