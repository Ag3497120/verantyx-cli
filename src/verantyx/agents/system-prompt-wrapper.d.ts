/**
 * SystemPromptWrapper ensures that the LLM Translator (Coder) receives ONLY the extracted
 * implementation details (Blueprint), and NEVER the raw user intent.
 * This prevents the LLM from trying to "think" or hallucinate outside the Swarm's consensus.
 */
export declare class SystemPromptWrapper {
    /**
     * Wraps the extracted JCross blueprint into a clean, constrained prompt for the LLM.
     */
    wrapForTranslation(extractedBlueprint: string): string;
}
//# sourceMappingURL=system-prompt-wrapper.d.ts.map