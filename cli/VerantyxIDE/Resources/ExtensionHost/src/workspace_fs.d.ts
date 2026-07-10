import { RPCClient } from './rpc';
import { Uri } from './types';
export declare class FileSystem {
    private rpc;
    constructor(rpc: RPCClient);
    stat(uri: Uri): Promise<any>;
    readDirectory(uri: Uri): Promise<[string, any][]>;
    createDirectory(uri: Uri): Promise<void>;
    readFile(uri: Uri): Promise<Uint8Array>;
    writeFile(uri: Uri, content: Uint8Array): Promise<void>;
    delete(uri: Uri, options?: {
        recursive?: boolean;
        useTrash?: boolean;
    }): Promise<void>;
    rename(source: Uri, target: Uri, options?: {
        overwrite?: boolean;
    }): Promise<void>;
}
//# sourceMappingURL=workspace_fs.d.ts.map