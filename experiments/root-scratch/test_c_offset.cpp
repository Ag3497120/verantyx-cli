#include <stdio.h>
#include <stdint.h>
#include <stddef.h>

#pragma pack(push, 1)
struct SharedHands {
    double poseTimestamp;
    double renderedTimestamp;
    float headTransform[16];
    float leftTransform[16];
    float rightTransform[16];
    uint8_t leftPinch;
    uint8_t rightPinch;
    uint32_t rightButtons;
    uint32_t leftButtons;
    float rightStickX;
    float rightStickY;
    float leftStickX;
    float leftStickY;
    float rightVelocity[3];
    float leftVelocity[3];
};
#pragma pack(pop)

int main() {
    printf("poseTimestamp: %zu\n", offsetof(struct SharedHands, poseTimestamp));
    printf("renderedTimestamp: %zu\n", offsetof(struct SharedHands, renderedTimestamp));
    printf("headTransform: %zu\n", offsetof(struct SharedHands, headTransform));
    printf("leftTransform: %zu\n", offsetof(struct SharedHands, leftTransform));
    printf("rightTransform: %zu\n", offsetof(struct SharedHands, rightTransform));
    printf("leftPinch: %zu\n", offsetof(struct SharedHands, leftPinch));
    printf("rightPinch: %zu\n", offsetof(struct SharedHands, rightPinch));
    printf("rightButtons: %zu\n", offsetof(struct SharedHands, rightButtons));
    printf("leftButtons: %zu\n", offsetof(struct SharedHands, leftButtons));
    return 0;
}
