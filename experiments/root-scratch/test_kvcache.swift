import MLX
import MLXLMCommon

MLX.GPU.set(cacheLimit: 0) // No need for GPU in test

let B = 1
let nH = 40
let L = 5
let hD = 128

let k = MLXArray.zeros([B, nH, L, hD])
let v = MLXArray.zeros([B, nH, L, hD])

let cache = KVCacheSimple()
let (kOut, vOut) = cache.update(keys: k, values: v)
print("Out shape:", kOut.shape)
