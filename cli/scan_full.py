import mmap, struct, os

path = os.path.expanduser("~/Verantyx_VR_Drive/SteamVR_Prefix/drive_c/vr_shared_frame.dat")
with open(path, "rb") as f:
    data = f.read(16 + 3840 * 1080 * 4)

seq, width, height, fmt = struct.unpack_from("<IIII", data, 0)
print(f"seq={seq} width={width} height={height} format={fmt}")

pixels = data[16:]

# Find max anywhere in frame
max_val = 0
max_pos = 0
for i in range(0, min(width * height * 4, len(pixels) - 4), 4):
    v = max(pixels[i], pixels[i+1], pixels[i+2])
    if v > max_val:
        max_val = v
        max_pos = i

px = max_pos // 4
x = px % width
y = px // width
b,g,r = pixels[max_pos], pixels[max_pos+1], pixels[max_pos+2]
print(f"Brightest pixel: x={x} y={y} B={b} G={g} R={r} val={max_val}")

# Histogram of brightness
buckets = [0] * 16
for i in range(0, min(width*height*4, len(pixels)-4), 4*100):  # sample 1%
    v = max(pixels[i], pixels[i+1], pixels[i+2])
    bucket = min(15, v // 16)
    buckets[bucket] += 1
print("Brightness histogram (0=black, 15=white):")
for i, c in enumerate(buckets):
    if c > 0: print(f"  {i*16:3d}-{i*16+15:3d}: {'#'*(c//10)} ({c})")
