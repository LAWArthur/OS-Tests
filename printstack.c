#define _GNU_SOURCE
#include <stdio.h>
#include <dlfcn.h>
typedef unsigned long long uint64;

void print_stackframe() {
    void **rbp, **rsp;
    asm volatile ("mov %%rbp, %0" : "=r"(rbp));
    asm volatile ("mov %%rsp, %0" : "=r"(rsp));

    printf("----- Stack trace begin -----\n");
    while ((uint64)rbp >= (uint64)rsp && ((uint64)rbp & 0x7) == 0) { // Very simple sanity check to prevent seg fault, for rbp should always be larger than rsp and aligned
        // printf("%p\n", rbp);
        void *ra = *(rbp + 1);
        Dl_info info;
        if (dladdr(ra, &info)) {
            printf("[%p] %s(%p)+%#tx (%s)\n", ra, info.dli_sname, info.dli_saddr, (char*)ra - (char*)info.dli_saddr, info.dli_fname);
        } else {
            printf("[%p] ???\n", ra);
        }
        rbp = (void **)(*rbp);
    }
    printf("----- Stack trace end -----\n");
}

void deep(int n){
    if(n == 0)print_stackframe();
    else deep(n-1);
}

int main() {
    deep(3);
    return 0;
}