import Foundation

// MARK: - Vera Data Types

/// Represents the data type of a VeraTensor.
/// Includes native support for GGUF quantization formats.
public enum VeraDType: String, Codable, Sendable {
    case float32 = "f32"
    case float16 = "f16"
    case bfloat16 = "bf16"
    case int32 = "i32"
    case int8 = "i8"
    
    // GGUF specific quantized types
    case q4_0 = "q4_0"
    case q4_1 = "q4_1"
    case q5_0 = "q5_0"
    case q5_1 = "q5_1"
    case q8_0 = "q8_0"
    
    // k-quants
    case q2_K = "q2_K"
    case q3_K = "q3_K"
    case q4_K = "q4_K"
    case q5_K = "q5_K"
    case q6_K = "q6_K"
    
    /// Returns the byte size per element. For block-quantized types (like q4_0),
    /// this returns the effective byte size per scalar (which is fractional),
    /// or throws/returns nil if byte size must be calculated per block.
    public var bytesPerScalar: Float {
        switch self {
        case .float32, .int32: return 4.0
        case .float16, .bfloat16: return 2.0
        case .int8: return 1.0
        case .q4_0, .q4_1, .q4_K: return 0.5 // Approximations; actual calculation needs block sizes
        case .q5_0, .q5_1, .q5_K: return 0.625
        case .q8_0: return 1.0
        case .q2_K: return 0.25
        case .q3_K: return 0.375
        case .q6_K: return 0.75
        }
    }
}

// MARK: - Vera Tensor

/// Represents a multi-dimensional array of elements in the computational graph.
public class VeraTensor: @unchecked Sendable {
    public let id: UUID
    public let shape: [Int]
    public let dtype: VeraDType
    
    /// The node that produces this tensor. If nil, this tensor is an input parameter or constant.
    public weak var sourceNode: VeraNode?
    
    /// Optional underlying memory pointer if this tensor is realized.
    public var rawData: UnsafeMutableRawPointer?
    
    public init(shape: [Int], dtype: VeraDType, sourceNode: VeraNode? = nil) {
        self.id = UUID()
        self.shape = shape
        self.dtype = dtype
        self.sourceNode = sourceNode
    }
}

// MARK: - Vera Operations

/// Defines the primitive computational operations in Vera IR.
public enum VeraOperation: Sendable {
    // Arithmetic
    case add
    case multiply
    case divide
    case subtract
    
    // Matrix Math
    case matmul
    
    // Activations
    case relu
    case silu
    case softmax
    
    // Normalization & Embeddings
    case layerNorm
    case rmsNorm
    case rotaryEmbedding
    
    // Dynamic JCross Routing
    /// JCross-driven dynamic routing operation.
    /// Conditionally executes tensor branches based on JCross 6-axis structural metadata.
    /// This avoids executing specific blocks (like FFN or Attention heads) if the semantic
    /// intent from JCross determines they are irrelevant for the current context.
    case jcrossRoute(axisMask: UInt8)
}

// MARK: - Vera Node

/// A node in the Vera computational graph representing an operation.
public class VeraNode: @unchecked Sendable {
    public let id: UUID
    public let operation: VeraOperation
    public let inputs: [VeraTensor]
    public var outputs: [VeraTensor] = []
    
    /// Used by backends to determine if the node has already been executed/realized.
    public var isEvaluated: Bool = false
    
    /// For dynamic routing operations (e.g. `jcrossRoute`), this closure evaluates at runtime
    /// whether this node and its downstream subgraph should actually be computed.
    public var routeCondition: (@Sendable () -> Bool)?
    
    public init(operation: VeraOperation, inputs: [VeraTensor]) {
        self.id = UUID()
        self.operation = operation
        self.inputs = inputs
    }
    
    /// Binds output tensors to this node.
    public func setOutputs(_ tensors: [VeraTensor]) {
        self.outputs = tensors
        for tensor in tensors {
            tensor.sourceNode = self
        }
    }
}
