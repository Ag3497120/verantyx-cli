import socket
import struct
import time
import sys
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

# Right Buttons Bitmask
BTN_A = 1 << 0
BTN_B = 1 << 1
BTN_ZR = 1 << 2
BTN_R3 = 1 << 3
BTN_PLUS = 1 << 4
BTN_R_SL = 1 << 5
BTN_R_SR = 1 << 6

# Left Buttons Bitmask
BTN_DPAD_UP = 1 << 0
BTN_DPAD_DOWN = 1 << 1
BTN_DPAD_LEFT = 1 << 2
BTN_DPAD_RIGHT = 1 << 3
BTN_ZL = 1 << 4
BTN_L3 = 1 << 5
BTN_MINUS = 1 << 6
BTN_L_SL = 1 << 7
BTN_L_SR = 1 << 8

def main():
    pygame.init()
    pygame.joystick.init()
    
    joystick = None
    if pygame.joystick.get_count() > 0:
        joystick = pygame.joystick.Joystick(0)
        joystick.init()
        print(f"Detected Gamepad: {joystick.get_name()}")
    else:
        print("No gamepad detected! You can use keyboard fallbacks instead.")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = ("127.0.0.1", 11002)

    print("Sending JoyconPacket (JOYC) to 127.0.0.1:11002...")

    screen = pygame.display.set_mode((400, 300))
    pygame.display.set_caption("Verantyx Joy-Con Tester")

    clock = pygame.time.Clock()

    while True:
        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
        except Exception as e:
            pass

        right_buttons = 0
        left_buttons = 0
        right_stick_x = 0.0
        right_stick_y = 0.0
        left_stick_x = 0.0
        left_stick_y = 0.0
        right_vel = [0.0, 0.0, 0.0]
        left_vel = [0.0, 0.0, 0.0]

        # Gamepad input
        if joystick:
            num_btns = joystick.get_numbuttons()
            
            # This mapping is approximate for standard SDL2 gamepads on macOS.
            # 0: A (South), 1: B (East), 2: X (West), 3: Y (North)
            # 4: -, 6: +
            # 7: L3, 8: R3
            # 9: L, 10: R
            # 11: D-Up, 12: D-Down, 13: D-Left, 14: D-Right
            
            if num_btns > 0 and joystick.get_button(0): right_buttons |= BTN_A
            if num_btns > 1 and joystick.get_button(1): right_buttons |= BTN_B
            if num_btns > 6 and joystick.get_button(6): right_buttons |= BTN_PLUS
            if num_btns > 8 and joystick.get_button(8): right_buttons |= BTN_R3
            
            if num_btns > 4 and joystick.get_button(4): left_buttons |= BTN_MINUS
            if num_btns > 7 and joystick.get_button(7): left_buttons |= BTN_L3
            if num_btns > 11 and joystick.get_button(11): left_buttons |= BTN_DPAD_UP
            if num_btns > 12 and joystick.get_button(12): left_buttons |= BTN_DPAD_DOWN
            if num_btns > 13 and joystick.get_button(13): left_buttons |= BTN_DPAD_LEFT
            if num_btns > 14 and joystick.get_button(14): left_buttons |= BTN_DPAD_RIGHT
            
            # Triggers as buttons or axes (depends on controller)
            if num_btns > 10 and joystick.get_button(10): right_buttons |= BTN_ZR
            if num_btns > 9 and joystick.get_button(9): left_buttons |= BTN_ZL
            
            # Map standard bumpers (L/R) to SL/SR so Grip works
            if num_btns > 5 and joystick.get_button(5): right_buttons |= BTN_R_SL # Right Bumper to R_SL
            if num_btns > 4 and joystick.get_button(4): left_buttons |= BTN_L_SL # Left Bumper to L_SL
            
            axes = joystick.get_numaxes()
            if axes >= 2:
                lx = joystick.get_axis(0)
                ly = joystick.get_axis(1)
                if abs(lx) > 0.15: left_stick_x = lx
                if abs(ly) > 0.15: left_stick_y = ly
            if axes >= 4:
                rx = joystick.get_axis(2)
                ry = joystick.get_axis(3)
                if abs(rx) > 0.15: right_stick_x = rx
                if abs(ry) > 0.15: right_stick_y = ry

        # Keyboard input fallback
        keys = pygame.key.get_pressed()
        if keys[pygame.K_SPACE]: 
            right_buttons |= BTN_ZR
            left_buttons |= BTN_ZL
        if keys[pygame.K_RETURN]: left_buttons |= BTN_ZL
        if keys[pygame.K_a]: right_buttons |= BTN_A
        if keys[pygame.K_b]: right_buttons |= BTN_B
        if keys[pygame.K_g]: 
            right_buttons |= BTN_R_SL
            left_buttons |= BTN_L_SL
        
        if keys[pygame.K_LEFT]: right_stick_x = -1.0
        if keys[pygame.K_RIGHT]: right_stick_x = 1.0
        if keys[pygame.K_UP]: right_stick_y = -1.0
        if keys[pygame.K_DOWN]: right_stick_y = 1.0

        if keys[pygame.K_w]: left_stick_y = -1.0
        if keys[pygame.K_s]: left_stick_y = 1.0
        if keys[pygame.K_a]: left_stick_x = -1.0
        if keys[pygame.K_d]: left_stick_x = 1.0

        # JoyconPacket structure: <III 10f
        # magic (I), rightButtons (I), leftButtons (I)
        # rightStickX, rightStickY, leftStickX, leftStickY (4f)
        # rightVelocityX, Y, Z (3f)
        # leftVelocityX, Y, Z (3f)
        
        packet = struct.pack("<IIIffffffffff",
                             0x4A4F5943, # "JOYC"
                             right_buttons,
                             left_buttons,
                             right_stick_x, right_stick_y,
                             left_stick_x, left_stick_y,
                             right_vel[0], right_vel[1], right_vel[2],
                             left_vel[0], left_vel[1], left_vel[2])

        has_input = (joystick is not None) or (right_buttons != 0) or (left_buttons != 0) or (right_stick_x != 0.0) or (right_stick_y != 0.0) or (left_stick_x != 0.0) or (left_stick_y != 0.0)
        if has_input:
            sock.sendto(packet, target)


        # Draw status
        screen.fill((30, 30, 30))
        font = pygame.font.SysFont(None, 24)
        text1 = font.render(f"R Btn: {bin(right_buttons)} L Btn: {bin(left_buttons)}", True, (255, 255, 255))
        screen.blit(text1, (20, 50))
        text2 = font.render(f"L Stick: {left_stick_x:.2f}, {left_stick_y:.2f}", True, (255, 255, 255))
        screen.blit(text2, (20, 100))
        text3 = font.render(f"R Stick: {right_stick_x:.2f}, {right_stick_y:.2f}", True, (255, 255, 255))
        screen.blit(text3, (20, 150))
        pygame.display.flip()

        clock.tick(60) # 60 Hz

if __name__ == "__main__":
    main()
