import Foundation
import Accelerate

public class LayerScout {
    
    public static func predict(input: [Float], w1: [Float], w2: [Float], inDim: Int, rank: Int, outDim: Int) -> [Float] {
        var hidden = [Float](repeating: 0.0, count: rank)
        
        input.withUnsafeBufferPointer { inPtr in
            w1.withUnsafeBufferPointer { w1Ptr in
                hidden.withUnsafeMutableBufferPointer { hPtr in
                    cblas_sgemv(CblasRowMajor, CblasTrans,
                                Int32(inDim), Int32(rank),
                                1.0, w1Ptr.baseAddress!, Int32(rank),
                                inPtr.baseAddress!, 1,
                                0.0, hPtr.baseAddress!, 1)
                }
            }
        }
        
        var output = [Float](repeating: 0.0, count: outDim)
        
        hidden.withUnsafeBufferPointer { hPtr in
            w2.withUnsafeBufferPointer { w2Ptr in
                output.withUnsafeMutableBufferPointer { outPtr in
                    cblas_sgemv(CblasRowMajor, CblasNoTrans,
                                Int32(outDim), Int32(rank),
                                1.0, w2Ptr.baseAddress!, Int32(rank),
                                hPtr.baseAddress!, 1,
                                0.0, outPtr.baseAddress!, 1)
                }
            }
        }
        
        return output
    }
    
    public static func predictWithMomentum(input: [Float], w1: [Float], w2: [Float], inDim: Int, rank: Int, outDim: Int, momentum: inout [Float], staticMap: [Float], momentumDecay: Float = 0.8, staticWeight: Float = 0.2, momentumWeight: Float = 0.3) -> [Float] {
        // Base prediction
        var baseOutput = predict(input: input, w1: w1, w2: w2, inDim: inDim, rank: rank, outDim: outDim)
        
        // Ensure momentum array size matches outDim
        if momentum.count != outDim {
            momentum = [Float](repeating: 0.0, count: outDim)
        }
        
        // Blend predictions
        for i in 0..<outDim {
            // The final score is a blend of the actual physical prediction and the momentum (where it was flowing).
            // We removed staticScore blending here because Static Map is now used for hard-pinning in the backend.
            let blended = (baseOutput[i] * (1.0 - momentumWeight)) + (momentum[i] * momentumWeight)
            baseOutput[i] = blended
            
            // Update momentum for the next layer (decayed)
            momentum[i] = blended * momentumDecay
        }
        
        return baseOutput
    }
}
