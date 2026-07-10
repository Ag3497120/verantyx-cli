import mmap, struct, os

path = os.path.expanduser("~/Verantyx_VR_Drive/SteamVR_Prefix/drive_c/vr_shared_frame.dat")
with open(path, "rb") as f:
    data = f.read(16 + 1920 * 1080 * 4)  # just read first eye

seq, width, height, fmt = struct.unpack_from("<IIII", data, 0)
print(f"seq={seq} width={width} height={height} format={fmt}")

pixels = data[16:16 + width//2 * height * 4]
max_b = max(pixels[0::4])
max_g = max(pixels[1::4])
max_r = max(pixels[2::4])
max_a = max(pixels[3::4])
print(f"Max channel values in LEFT eye: B={max_b} G={max_g} R={max_r} A={max_a}")

# Sample center pixel
cx = (width//2) // 2
cy = height // 2
off = (cy * (width//2) + cx) * 4
b,g,r,a = pixels[off], pixels[off+1], pixels[off+2], pixels[off+3]
print(f"Center pixel: B={b} G={g} R={r} A={a}")
