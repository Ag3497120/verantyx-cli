#include <windows.h>
#include <stdio.h>
int main() {
    HMODULE h = LoadLibraryA("d3d11_real.dll");
    printf("Load d3d11_real.dll: %p, Error: %d\n", h, GetLastError());
    return 0;
}
