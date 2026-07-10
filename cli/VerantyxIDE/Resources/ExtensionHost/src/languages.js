"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Languages = void 0;
const rpc_1 = require("./rpc");
const types_1 = require("./types");
const vscode_1 = require("./vscode"); // Assuming it's in vscode.ts
class Languages {
    getDocument;
    rpc;
    providers = new Map();
    providerIdCounter = 0;
    constructor(rpc, getDocument) {
        this.getDocument = getDocument;
        this.rpc = rpc;
        // Listen for requests from Swift to invoke providers
        this.rpc.onNotification('languages.invokeProvider', async (params) => {
            const provider = this.providers.get(params.providerId);
            if (provider && typeof provider[params.method] === 'function') {
                try {
                    // Resolve Virtual Document
                    const doc = this.getDocument(params.args.uri);
                    if (!doc)
                        throw new Error('Document not found');
                    const position = new types_1.Position(params.args.position.line, params.args.position.character);
                    const result = await Promise.resolve(provider[params.method](doc, position, { isCancellationRequested: false }));
                    this.rpc.sendNotification('languages.invokeProvider.response', { requestId: params.requestId, result });
                }
                catch (err) {
                    this.rpc.sendNotification('languages.invokeProvider.response', { requestId: params.requestId, error: err.toString() });
                }
            }
            else {
                this.rpc.sendNotification('languages.invokeProvider.response', { requestId: params.requestId, error: `Provider/method not found` });
            }
        });
    }
    registerCompletionItemProvider(selector, provider, ...triggerCharacters) {
        return this.registerProvider('CompletionItemProvider', selector, provider, { triggerCharacters });
    }
    registerHoverProvider(selector, provider) {
        return this.registerProvider('HoverProvider', selector, provider);
    }
    registerDefinitionProvider(selector, provider) {
        return this.registerProvider('DefinitionProvider', selector, provider);
    }
    registerProvider(type, selector, provider, extraOptions) {
        const id = `${type}-${this.providerIdCounter++}`;
        this.providers.set(id, provider);
        // Notify Swift that a new language provider is available for the given selector
        this.rpc.sendNotification('languages.registerProvider', {
            id,
            type,
            selector,
            options: extraOptions
        });
        return new types_1.Disposable(() => {
            this.providers.delete(id);
            this.rpc.sendNotification('languages.unregisterProvider', { id });
        });
    }
}
exports.Languages = Languages;
//# sourceMappingURL=languages.js.map