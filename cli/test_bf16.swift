import Foundation

func bf16_to_f32(_ bfloat_val: UInt16) -> Float {
    let val32 = UInt32(bfloat_val) << 16
    return Float(bitPattern: val32)
}

let bf16_val: UInt16 = 0x3f80 // 1.0 in bf16
print("bf16 0x3f80 ->", bf16_to_f32(bf16_val))

let bf16_val2: UInt16 = 0xc000 // -2.0 in bf16
print("bf16 0xc000 ->", bf16_to_f32(bf16_val2))
