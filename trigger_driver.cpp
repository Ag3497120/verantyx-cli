#include <openvr.h>
#include <iostream>
#include <thread>
#include <chrono>

int main(int argc, char** argv) {
    vr::EVRInitError eError = vr::VRInitError_None;
    vr::IVRSystem* pVRSystem = vr::VR_Init(&eError, vr::VRApplication_Background);
    
    if (eError != vr::VRInitError_None) {
        std::cerr << "VR_Init failed: " << vr::VR_GetVRInitErrorAsEnglishDescription(eError) << " (" << eError << ")" << std::endl;
        return 1;
    }
    
    std::cout << "Successfully connected to SteamVR as VRApplication_Background!" << std::endl;
    
    // Wait for 10 seconds to keep the connection alive and let drivers load
    std::cout << "Waiting for 10 seconds..." << std::endl;
    std::this_thread::sleep_for(std::chrono::seconds(10));
    
    vr::VR_Shutdown();
    return 0;
}
