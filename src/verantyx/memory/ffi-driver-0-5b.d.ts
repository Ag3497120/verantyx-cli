export declare class JCrossEngineDriver05B {
    private enginePtr;
    constructor(jgenPath: string);
    projectSubspace(layerName: string, inputVector: Float32Array, outputLen: number): Float32Array;
    resynthesizeVector(layerName: string, inputVector: Float32Array, outputLen: number, temperature?: number): Float32Array;
    executePuzzleInference(layerName: string, inputVector: Float32Array): {
        token: number;
        entropy: number;
    };
    optimizeThoughtInPlace(layerName: string, inputVector: Float32Array, maxSteps?: number, lr?: number, temperature?: number): number;
    executeGenerationLoop(startToken: number, maxTokens: number): Uint32Array;
    executeWorkerForward(tokens: Uint32Array, outDim: number): Float32Array;
    destroy(): void;
}
export declare class JCrossTokenizerDriver {
    private tokenizerPtr;
    constructor(pathStr: string);
    decode(tokenId: number): string;
    encode(text: string): number[];
    destroy(): void;
}
//# sourceMappingURL=ffi-driver-0-5b.d.ts.map