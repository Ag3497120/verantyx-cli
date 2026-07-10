#include <windows.h>
#include <stdio.h>
int main() {
    HMODULE h = LoadLibraryA("dxgi_real.dll");
    printf("Load dxgi_real.dll: %p, Error: %d\n", h, GetLastError());
    return 0;
}
