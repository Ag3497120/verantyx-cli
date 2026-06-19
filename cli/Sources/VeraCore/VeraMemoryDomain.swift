import Foundation

// MARK: - Vera Memory Architecture

/// Represents the fundamental memory topology of the target hardware.
public enum VeraMemoryArchitecture {
    /// Group A: Unified Memory Architecture (Apple Silicon, Snapdragon, Ryzen AI).
    /// CPU and GPU/NPU share the same physical RAM. Data can be accessed
    /// via zero-copy pointers without explicit Host-to-Device transfers.
    case unified(zeroCopyEnabled: Bool)
    
    /// Group B: Split Memory Architecture (Discrete NVIDIA/AMD GPUs).
    /// Requires explicit PCIe bus transfers (Host-to-Device / Device-to-Host)
    /// to move data between main RAM and VRAM.
    case split(pcieBandwidthGBs: Float)
}

// MARK: - Vera Memory Manager Protocol

/// Defines the contract for memory allocation and synchronization across different hardware backends.
public protocol VeraMemoryManager: Sendable {
    
    /// The physical memory architecture this manager represents.
    var architecture: VeraMemoryArchitecture { get }
    
    /// Allocates contiguous bytes.
    /// - For Group A (Unified), this returns a pointer mapped directly to device memory.
    /// - For Group B (Split), this may allocate pinned Host memory, or allocate Device memory depending on the backend implementation.
    func allocate(bytes: Int) -> UnsafeMutableRawPointer
    
    /// Deallocates memory.
    func deallocate(pointer: UnsafeMutableRawPointer)
    
    /// Synchronizes data from Host (RAM) to Device (VRAM/NPU memory).
    /// - For Group A (Unified): This is typically a no-op or cache flush.
    /// - For Group B (Split): This triggers a PCIe DMA transfer.
    func syncHostToDevice(pointer: UnsafeRawPointer, size: Int)
    
    /// Synchronizes data from Device (VRAM/NPU memory) to Host (RAM).
    func syncDeviceToHost(pointer: UnsafeRawPointer, size: Int)
}
