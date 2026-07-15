#include <windows.h>
#include <iostream>

int main() {
    HMODULE h = LoadLibraryExA("C:\\Program Files (x86)\\Steam\\steamapps\\common\\SteamVR\\bin\\vrclient_x64.dll", NULL, LOAD_WITH_ALTERED_SEARCH_PATH);
    if (!h) {
        std::cerr << "LoadLibraryExA failed: " << GetLastError() << std::endl;
        return 1;
    }
    std::cout << "LoadLibraryExA succeeded! Handle: " << h << std::endl;
    
    void* pfn = (void*)GetProcAddress(h, "VRClientCoreFactory");
    if (!pfn) {
        std::cerr << "GetProcAddress failed: " << GetLastError() << std::endl;
        return 1;
    }
    std::cout << "GetProcAddress succeeded! Pointer: " << pfn << std::endl;
    return 0;
}
