/**
 * AgentOrchestrator manages the Swarm (Commander, Worker, Scout) and the Translator (Coder).
 */
export declare class AgentOrchestrator {
    private memory;
    private wrapper;
    constructor(workspaceRoot: string);
    /**
     * Initializes the session according to Verantyx protocol.
     */
    initializeSession(): void;
    /**
     * Recontextualization protocol.
     */
    private guide;
    /**
     * Dispatches the Commander to translate user intent into a cognitive anchor.
     */
    dispatchCommander(userIntent: string): Float32Array;
    /**
     * Dispatches the Worker to perform JCross Puzzle Inference (Latent Resonance Search).
     */
    dispatchWorker(anchor: Float32Array): string;
    /**
     * Dispatches the Coder to translate the extracted blueprint into the final output.
     */
    dispatchCoder(blueprint: string): string;
}
//# sourceMappingURL=orchestrator.d.ts.map