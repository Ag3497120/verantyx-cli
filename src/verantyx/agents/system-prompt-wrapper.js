"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SystemPromptWrapper = void 0;
/**
 * SystemPromptWrapper ensures that the LLM Translator (Coder) receives ONLY the extracted
 * implementation details (Blueprint), and NEVER the raw user intent.
 * This prevents the LLM from trying to "think" or hallucinate outside the Swarm's consensus.
 */
class SystemPromptWrapper {
    /**
     * Wraps the extracted JCross blueprint into a clean, constrained prompt for the LLM.
     */
    wrapForTranslation(extractedBlueprint) {
        return `[SYSTEM]
You are a pure syntax translator. You have no domain knowledge of the problem.
Your ONLY task is to translate the following provided implementation blueprint into valid syntax.
Do not add any logic or thinking outside of what is explicitly detailed in the blueprint.

[IMPLEMENTATION BLUEPRINT]
${extractedBlueprint}

[OUTPUT EXPECTATION]
Output the translated code/text directly. Do not include <think> tags.
`;
    }
}
exports.SystemPromptWrapper = SystemPromptWrapper;
//# sourceMappingURL=system-prompt-wrapper.js.map