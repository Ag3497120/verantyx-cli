import { RPCClient } from './rpc';
import { Disposable, Position, Range, Location, Uri } from './types';
import { Commands } from './commands';
import { Languages } from './languages';
import { FileSystem } from './workspace_fs';
export interface Event<T> {
    (listener: (e: T) => any, thisArgs?: any, disposables?: any[]): {
        dispose(): void;
    };
}
export declare class EventEmitterImpl<T> {
    private emitter;
    get event(): Event<T>;
    fire(data: T): void;
}
export declare class TextDocument {
    readonly uri: any;
    readonly fileName: string;
    readonly languageId: string;
    readonly version: number;
    readonly isDirty: boolean;
    readonly isClosed: boolean;
    private lines;
    constructor(uri: string, languageId: string, version: number, content: string);
    getText(): string;
    applyChange(range: {
        startLine: number;
        endLine: number;
    }, newText: string): void;
}
export declare class Webview {
    private rpc;
    readonly panelId: string;
    private _html;
    private _onDidReceiveMessage;
    readonly onDidReceiveMessage: Event<any>;
    constructor(rpc: RPCClient, panelId: string);
    get html(): string;
    set html(value: string);
    postMessage(message: any): Promise<boolean>;
}
export declare class WebviewPanel {
    readonly webview: Webview;
    title: string;
    private _onDidDispose;
    readonly onDidDispose: Event<void>;
    constructor(rpc: RPCClient, panelId: string, title: string);
    dispose(): void;
}
export declare class Window {
    private rpc;
    private ext;
    constructor(rpc: RPCClient);
    createOutputChannel(name: string): import("./window").OutputChannel;
    showQuickPick(items: any[], options?: any): Promise<any>;
    showInputBox(options?: any): Promise<string | undefined>;
    createWebviewPanel(viewType: string, title: string, showOptions: any, options?: any): WebviewPanel;
    showInformationMessage(message: string, ...items: string[]): Promise<string | undefined>;
    showErrorMessage(message: string, ...items: string[]): Promise<string | undefined>;
}
export declare class Workspace {
    private rpc;
    textDocuments: TextDocument[];
    fs: FileSystem;
    private _onDidChangeTextDocument;
    readonly onDidChangeTextDocument: Event<any>;
    private _onDidOpenTextDocument;
    readonly onDidOpenTextDocument: Event<TextDocument>;
    constructor(rpc: RPCClient);
    get rootPath(): string | undefined;
    getConfiguration(section?: string): any;
}
export declare function createVSCodeAPI(rpc: RPCClient): {
    window: Window;
    workspace: Workspace;
    commands: Commands;
    languages: Languages;
    EventEmitter: typeof EventEmitterImpl;
    Disposable: typeof Disposable;
    Position: typeof Position;
    Range: typeof Range;
    Location: typeof Location;
    Uri: typeof Uri;
};
//# sourceMappingURL=vscode.d.ts.map