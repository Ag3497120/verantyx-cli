import Foundation

let f32: Float = .nan
let arr = [1.0, 5.0, f32, -2.0, 3.0]
var best_idx = 0
var max_val = -1e9
for i in 0..<arr.count {
    if arr[i] > max_val {
        max_val = arr[i]
        best_idx = i
    }
}
print("Max idx:", best_idx)
