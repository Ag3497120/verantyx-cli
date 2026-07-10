import socket
import struct
import time

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = ("127.0.0.1", 11002)

    BTN_ZR = 1 << 2
    BTN_ZL = 1 << 4

    packet = struct.pack("<IIIffffffffff",
                         0x4A4F5943, # "JOYC"
                         BTN_ZR,     # right_buttons
                         BTN_ZL,     # left_buttons
                         0.0, 0.0,   # right_stick
                         0.0, 0.0,   # left_stick
                         0.0, 0.0, 0.0, # right_vel
                         0.0, 0.0, 0.0) # left_vel

    empty_packet = struct.pack("<IIIffffffffff",
                               0x4A4F5943, 0, 0,
                               0.0, 0.0, 0.0, 0.0,
                               0.0, 0.0, 0.0,
                               0.0, 0.0, 0.0)

    print("Spamming trigger packets...")
    for i in range(100):
        # Press
        sock.sendto(packet, target)
        time.sleep(0.1)
        # Release
        sock.sendto(empty_packet, target)
        time.sleep(0.1)
        print(f"Sent toggle {i}")

if __name__ == "__main__":
    main()
