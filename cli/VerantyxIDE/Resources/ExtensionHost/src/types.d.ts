import { URI } from 'vscode-uri';
export declare class Disposable {
    static from(...disposables: {
        dispose(): any;
    }[]): Disposable;
    private callOnDispose?;
    constructor(callOnDispose: () => any);
    dispose(): void;
}
export declare class Position {
    readonly line: number;
    readonly character: number;
    constructor(line: number, character: number);
    isBefore(other: Position): boolean;
}
export declare class Range {
    readonly start: Position;
    readonly end: Position;
    constructor(startLine: number, startCharacter: number, endLine: number, endCharacter: number);
    constructor(start: Position, end: Position);
}
export declare class Location {
    uri: URI;
    range: Range;
    constructor(uri: URI, rangeOrPosition: Range | Position);
}
export { URI as Uri };
//# sourceMappingURL=types.d.ts.map