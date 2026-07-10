/**
 * Parses and searches the SPATIAL_INDEX.jcross binary structure.
 */
export declare class SpatialIndex {
    private indexPath;
    constructor(workspaceRoot: string);
    /**
     * Reads the JCross spatial index and loads available clusters.
     */
    loadIndex(): void;
    /**
     * Performs a Latent Resonance Search across the spatial index.
     * @param queryVector The encoded thought vector to search for.
     */
    search(queryVector: Float32Array): string[];
}
//# sourceMappingURL=spatial-index.d.ts.map