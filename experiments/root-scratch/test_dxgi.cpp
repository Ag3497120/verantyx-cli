#include <windows.h>
#include <stdio.h>
int main() {
    HMODULE h = LoadLibraryA("dxgi.dll");
    if (h) printf("Loaded DXGI: %p\n", h);
    else printf("Failed to load DXGI\n");
    return 0;
}
