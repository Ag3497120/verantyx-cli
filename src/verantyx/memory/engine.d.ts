/**
 * MemoryEngine handles CRUD operations for the Verantyx Memory Refresh System.
 * It manages Zone A (RAM), Zone B (SSD Permanent), and Zone C (Auto-Archiving).
 */
export declare class MemoryEngine {
    private zoneBPath;
    constructor(workspaceRoot: string);
    /**
     * Initializes the memory engine and injects the front layer context.
     */
    boot(): void;
    /**
     * Autonomously saves important context to Zone B (Eternal Memory).
     */
    remember(context: string, label: string): void;
    /**
     * Search-First Protocol: Checks past memory before taking action.
     */
    search(query: string): string[];
}
//# sourceMappingURL=engine.d.ts.map