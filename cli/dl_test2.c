#include <dlfcn.h>
#include <stdio.h>
int main() {
    void* handle = dlopen("/Applications/Game Porting Toolkit.app/Contents/Resources/wine/lib/wine/x86_64-unix/d3d11.so", RTLD_NOW);
    if (!handle) {
        printf("Error: %s\n", dlerror());
    } else {
        printf("Success\n");
    }
    return 0;
}
