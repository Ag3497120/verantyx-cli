/**
 * Gatekeeper manages Virtual File System (VFS) boundaries and secures memory access.
 * It ensures agents only read/write from authorized zones.
 */
export declare class Gatekeeper {
    private allowedZones;
    constructor(workspaceRoot: string);
    /**
     * Resolves and validates a virtual path to ensure it is within allowed zones.
     */
    resolvePath(virtualPath: string): string;
}
//# sourceMappingURL=gatekeeper.d.ts.map