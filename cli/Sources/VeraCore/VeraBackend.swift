import Foundation

// MARK: - Vera Executable Kernel

/// Represents a compiled, hardware-specific execution plan.
/// Backends (like Metal, CUDA, DirectML) will implement this protocol
/// to wrap their specific compute shaders or neural network operations.
public protocol VeraExecutableKernel: Sendable {
    /// Dispatches the compute workload to the hardware accelerator.
    func dispatch() async throws
}

// MARK: - Vera Backend

/// Defines a hardware abstraction layer for executing Vera computational graphs.
public protocol VeraBackend: Sendable {
    
    /// The unique name of the backend (e.g., "Metal", "CUDA", "Hexagon").
    var name: String { get }
    
    /// The memory manager associated with this backend, exposing the Group A / Group B architecture.
    var memoryManager: VeraMemoryManager { get }
    
    /// Compiles a VeraNode (and its parent graph) into a hardware-specific executable kernel.
    /// This process involves operation mapping, fusion, and memory allocation.
    /// - Parameter node: The terminal node of the computational graph to compile.
    /// - Returns: A compiled kernel ready for execution.
    func compile(graph node: VeraNode) throws -> VeraExecutableKernel
    
    /// Compiles a dynamic routing block (JCross MoE simulation) into an executable kernel.
    func compileDynamicRoute(node: VeraNode, mask: UInt8) throws -> VeraExecutableKernel
    
    /// Executes the compiled kernel on the target hardware.
    func execute(kernel: VeraExecutableKernel) async throws
}
