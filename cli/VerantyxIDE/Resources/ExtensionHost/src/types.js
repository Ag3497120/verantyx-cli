"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Uri = exports.Location = exports.Range = exports.Position = exports.Disposable = void 0;
const vscode_uri_1 = require("vscode-uri");
Object.defineProperty(exports, "Uri", { enumerable: true, get: function () { return vscode_uri_1.URI; } });
class Disposable {
    static from(...disposables) {
        return new Disposable(() => {
            for (const d of disposables) {
                if (d && typeof d.dispose === 'function') {
                    d.dispose();
                }
            }
        });
    }
    callOnDispose;
    constructor(callOnDispose) {
        this.callOnDispose = callOnDispose;
    }
    dispose() {
        if (this.callOnDispose) {
            this.callOnDispose();
            this.callOnDispose = undefined;
        }
    }
}
exports.Disposable = Disposable;
class Position {
    line;
    character;
    constructor(line, character) {
        this.line = line;
        this.character = character;
    }
    isBefore(other) {
        if (this.line < other.line)
            return true;
        if (this.line === other.line)
            return this.character < other.character;
        return false;
    }
}
exports.Position = Position;
class Range {
    start;
    end;
    constructor(startLineOrStart, startCharacterOrEnd, endLine, endCharacter) {
        if (typeof startLineOrStart === 'number') {
            this.start = new Position(startLineOrStart, startCharacterOrEnd);
            this.end = new Position(endLine, endCharacter);
        }
        else {
            this.start = startLineOrStart;
            this.end = startCharacterOrEnd;
        }
    }
}
exports.Range = Range;
class Location {
    uri;
    range;
    constructor(uri, rangeOrPosition) {
        this.uri = uri;
        if (rangeOrPosition instanceof Position) {
            this.range = new Range(rangeOrPosition, rangeOrPosition);
        }
        else {
            this.range = rangeOrPosition;
        }
    }
}
exports.Location = Location;
//# sourceMappingURL=types.js.map