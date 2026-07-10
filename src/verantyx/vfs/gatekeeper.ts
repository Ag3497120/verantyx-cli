import * as path from 'path';
import * as fs from 'fs';

/**
 * Gatekeeper manages Virtual File System (VFS) boundaries and secures memory access.
 * It ensures agents only read/write from authorized zones.
 */
export class Gatekeeper {
    private allowedZones: string[];

    constructor(workspaceRoot: string) {
        this.allowedZones = [
            workspaceRoot,
            path.join(workspaceRoot, '.verantyx_chrono')
        ];
    }

    /**
     * Resolves and validates a virtual path to ensure it is within allowed zones.
     */
    public resolvePath(virtualPath: string): string {
        const absolutePath = path.resolve(virtualPath);
        const isAllowed = this.allowedZones.some(zone => absolutePath.startsWith(zone));
        
        if (!isAllowed) {
            throw new Error(`[Gatekeeper] Access Denied: Path ${virtualPath} is outside allowed memory zones.`);
        }
        
        return absolutePath;
    }
}
