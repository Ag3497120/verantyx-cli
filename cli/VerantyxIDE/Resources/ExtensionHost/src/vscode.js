"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Workspace = exports.Window = exports.WebviewPanel = exports.Webview = exports.TextDocument = exports.EventEmitterImpl = void 0;
exports.createVSCodeAPI = createVSCodeAPI;
const rpc_1 = require("./rpc");
const events_1 = require("events");
const types_1 = require("./types");
const commands_1 = require("./commands");
const languages_1 = require("./languages");
const window_1 = require("./window");
const workspace_fs_1 = require("./workspace_fs");
class EventEmitterImpl {
    emitter = new events_1.EventEmitter();
    get event() {
        return (listener, thisArgs, disposables) => {
            const boundListener = thisArgs ? listener.bind(thisArgs) : listener;
            this.emitter.on('event', boundListener);
            const disposable = {
                dispose: () => {
                    this.emitter.removeListener('event', boundListener);
                }
            };
            if (disposables) {
                disposables.push(disposable);
            }
            return disposable;
        };
    }
    fire(data) {
        this.emitter.emit('event', data);
    }
}
exports.EventEmitterImpl = EventEmitterImpl;
// -----------------------------------------------------------------------------
// Text Document Emulation
// -----------------------------------------------------------------------------
class TextDocument {
    uri;
    fileName;
    languageId;
    version;
    isDirty;
    isClosed;
    lines;
    constructor(uri, languageId, version, content) {
        this.uri = { fsPath: uri, toString: () => uri };
        this.fileName = uri;
        this.languageId = languageId;
        this.version = version;
        this.isDirty = false;
        this.isClosed = false;
        this.lines = content.split('\n');
    }
    getText() {
        return this.lines.join('\n');
    }
    applyChange(range, newText) {
        // Enterprise robustness: apply minimal range edits to the virtual document
        // In a real scenario, this involves column-level ranges. For now, we do line-level.
        const newLines = newText.split('\n');
        this.lines.splice(range.startLine, range.endLine - range.startLine + 1, ...newLines);
        // version would increment here ideally
    }
}
exports.TextDocument = TextDocument;
// -----------------------------------------------------------------------------
// Webview Emulation
// -----------------------------------------------------------------------------
class Webview {
    rpc;
    panelId;
    _html = '';
    _onDidReceiveMessage = new EventEmitterImpl();
    onDidReceiveMessage = this._onDidReceiveMessage.event;
    constructor(rpc, panelId) {
        this.rpc = rpc;
        this.panelId = panelId;
        // Listen for messages from the Swift Webview to the extension
        this.rpc.onNotification(`webview.onDidReceiveMessage.${panelId}`, (message) => {
            this._onDidReceiveMessage.fire(message);
        });
    }
    get html() {
        return this._html;
    }
    set html(value) {
        this._html = value;
        // Send the updated HTML to Swift
        this.rpc.sendNotification('webview.updateHTML', { panelId: this.panelId, html: value });
    }
    async postMessage(message) {
        await this.rpc.sendRequest('webview.postMessage', { panelId: this.panelId, message });
        return true;
    }
}
exports.Webview = Webview;
class WebviewPanel {
    webview;
    title;
    _onDidDispose = new EventEmitterImpl();
    onDidDispose = this._onDidDispose.event;
    constructor(rpc, panelId, title) {
        this.title = title;
        this.webview = new Webview(rpc, panelId);
        rpc.onNotification(`webview.onDidDispose.${panelId}`, () => {
            this._onDidDispose.fire();
        });
    }
    dispose() {
        this.webview['rpc'].sendNotification('webview.dispose', { panelId: this.webview.panelId });
        this._onDidDispose.fire();
    }
}
exports.WebviewPanel = WebviewPanel;
// -----------------------------------------------------------------------------
// VS Code Namespaces
// -----------------------------------------------------------------------------
class Window {
    rpc;
    ext;
    constructor(rpc) {
        this.rpc = rpc;
        this.ext = new window_1.WindowExt(rpc);
    }
    createOutputChannel(name) {
        return this.ext.createOutputChannel(name);
    }
    showQuickPick(items, options) {
        return this.ext.showQuickPick(items, options);
    }
    showInputBox(options) {
        return this.ext.showInputBox(options);
    }
    createWebviewPanel(viewType, title, showOptions, options) {
        // Generate a unique ID for this panel instance
        const panelId = `${viewType}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        // Instruct Swift to open a WKWebView native panel
        this.rpc.sendNotification('window.createWebviewPanel', {
            panelId,
            viewType,
            title,
            showOptions,
            options
        });
        return new WebviewPanel(this.rpc, panelId, title);
    }
    async showInformationMessage(message, ...items) {
        const response = await this.rpc.sendRequest('window.showInformationMessage', { message, items });
        return response;
    }
    async showErrorMessage(message, ...items) {
        const response = await this.rpc.sendRequest('window.showErrorMessage', { message, items });
        return response;
    }
}
exports.Window = Window;
class Workspace {
    rpc;
    textDocuments = [];
    fs;
    // Events
    _onDidChangeTextDocument = new EventEmitterImpl();
    onDidChangeTextDocument = this._onDidChangeTextDocument.event;
    _onDidOpenTextDocument = new EventEmitterImpl();
    onDidOpenTextDocument = this._onDidOpenTextDocument.event;
    constructor(rpc) {
        this.rpc = rpc;
        this.fs = new workspace_fs_1.FileSystem(rpc);
        // Listen for IPC messages from Swift to sync the virtual text documents
        this.rpc.onNotification('workspace.didOpenTextDocument', (params) => {
            const doc = new TextDocument(params.uri, params.languageId, params.version, params.text);
            this.textDocuments.push(doc);
            this._onDidOpenTextDocument.fire(doc);
        });
        this.rpc.onNotification('workspace.didChangeTextDocument', (params) => {
            const doc = this.textDocuments.find(d => d.fileName === params.uri);
            if (doc) {
                doc.applyChange(params.range, params.text);
                // Fire the event so extensions know about the change
                this._onDidChangeTextDocument.fire({
                    document: doc,
                    contentChanges: [{ range: params.range, text: params.text }]
                });
            }
        });
        this.rpc.onNotification('workspace.didCloseTextDocument', (params) => {
            this.textDocuments = this.textDocuments.filter(d => d.fileName !== params.uri);
        });
    }
    get rootPath() {
        return process.cwd();
    }
    getConfiguration(section) {
        // Simple mock for now
        return {
            get: (key, defaultValue) => defaultValue,
            update: async (key, value) => {
                await this.rpc.sendRequest('workspace.getConfiguration.update', { section, key, value });
            }
        };
    }
}
exports.Workspace = Workspace;
function createVSCodeAPI(rpc) {
    const workspaceObj = new Workspace(rpc);
    return {
        window: new Window(rpc),
        workspace: workspaceObj,
        commands: new commands_1.Commands(rpc),
        languages: new languages_1.Languages(rpc, (uri) => workspaceObj.textDocuments.find(d => d.fileName === uri)),
        EventEmitter: EventEmitterImpl,
        Disposable: types_1.Disposable,
        Position: types_1.Position,
        Range: types_1.Range,
        Location: types_1.Location,
        Uri: types_1.Uri
    };
}
//# sourceMappingURL=vscode.js.map