#include <windows.h>
#include <d3d11.h>
#include <stdio.h>

int main() {
    WNDCLASSA wc = {0};
    wc.lpfnWndProc = DefWindowProc;
    wc.hInstance = GetModuleHandle(NULL);
    wc.lpszClassName = "DummyClass";
    RegisterClassA(&wc);
    HWND hwnd = CreateWindowA("DummyClass", "Dummy", WS_OVERLAPPEDWINDOW | WS_VISIBLE, 0, 0, 100, 100, NULL, NULL, wc.hInstance, NULL);
    
    MSG msg;
    for (int i = 0; i < 10; ++i) {
        if (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
            TranslateMessage(&msg);
            DispatchMessage(&msg);
        }
        Sleep(10);
    }

    HMODULE hD3D11 = LoadLibraryA("d3d11.dll");
    typedef HRESULT (WINAPI *PFN_D3D11_CREATE_DEVICE)(IDXGIAdapter*, D3D_DRIVER_TYPE, HMODULE, UINT, const D3D_FEATURE_LEVEL*, UINT, UINT, ID3D11Device**, D3D_FEATURE_LEVEL*, ID3D11DeviceContext**);
    PFN_D3D11_CREATE_DEVICE pD3D11CreateDevice = (PFN_D3D11_CREATE_DEVICE)GetProcAddress(hD3D11, "D3D11CreateDevice");
    
    ID3D11Device* pDevice = nullptr;
    ID3D11DeviceContext* pCtx = nullptr;
    D3D_FEATURE_LEVEL fl;
    HRESULT hr = pD3D11CreateDevice(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, 0, nullptr, 0, D3D11_SDK_VERSION, &pDevice, &fl, &pCtx);
    
    printf("D3D11CreateDevice Result: %x\n", hr);
    if (SUCCEEDED(hr)) {
        printf("Device Created! Feature Level: %x\n", fl);
    }
    return 0;
}
