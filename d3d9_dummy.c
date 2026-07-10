#include <windows.h>

void* WINAPI Direct3DCreate9(UINT SDKVersion) {
    return NULL;
}

HRESULT WINAPI Direct3DCreate9Ex(UINT SDKVersion, void** ppD3D) {
    if (ppD3D) {
        *ppD3D = NULL;
    }
    return 0x80004001; // E_NOTIMPL
}

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    return TRUE;
}
