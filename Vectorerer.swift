// File: /Users/yourname/Documents/MyProjecter/Vectorerer.swift

import Foundation

public class Vectorerer {
    public var x: Double
    public var y: Double

    public init(x: Double, y: Double) {
        self.x = x
// File: Vectorerer.swift

import Foundation

struct Vector {
    var components: [Double]
}

extension Vectorer {
    init(components: [Double]) {
        self.components = components
    }

    mutating func scale(factor: Double) {
        for i