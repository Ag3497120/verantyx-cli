#include <windows.h>
#include <stdio.h>
int main() {
    FILE* f = fopen("Z:\\Users\\motonishikoudai\\verantyx-cli\\cli\\env_dump2.txt", "w");
    if (!f) return 1;
    LPCH env = GetEnvironmentStrings();
    LPSTR p = (LPSTR)env;
    while (*p) {
        fprintf(f, "%s\n", p);
        p += strlen(p) + 1;
    }
    FreeEnvironmentStrings(env);
    fclose(f);
    return 0;
}
