export interface SWEBenchInstance {
    instance_id: string;
    text: string;
    repo?: string;
    base_commit?: string;
    [key: string]: any;
}
export interface SWEBenchPrediction {
    instance_id: string;
    model_patch: string;
    model_name_or_path: string;
}
export declare class SWEBenchHarness05B {
    private jgenPath;
    private tokenizerPath;
    private hiddenDim;
    private worker;
    private coder;
    private tokenizer;
    constructor(jgenPath: string, tokenizerPath: string, hiddenDim?: number);
    initialize(): Promise<void>;
    evaluate(inputJsonl: string, outputJsonl: string): Promise<void>;
    private processInstance;
    private extractPatch;
    destroy(): void;
}
//# sourceMappingURL=swe-bench-harness-0-5b.d.ts.map