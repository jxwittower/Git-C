#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef int (__stdcall *PFN_INIT)(char *, void *);
typedef void (__stdcall *PFN_FINI)(void);

static HMODULE g_module;

static int report_exception(EXCEPTION_POINTERS *ep, int which)
{
    uintptr_t base = (uintptr_t)g_module;
    uintptr_t addr = (uintptr_t)ep->ExceptionRecord->ExceptionAddress;
    DWORD code = ep->ExceptionRecord->ExceptionCode;
    printf("CASE=%d EXCEPTION_CODE=0x%08lX EXCEPTION_ADDRESS=0x%08lX RVA=0x%08lX\n",
           which, (unsigned long)code, (unsigned long)addr,
           (unsigned long)(addr - base));
    if (code == EXCEPTION_ACCESS_VIOLATION && ep->ExceptionRecord->NumberParameters >= 2) {
        printf("AV_OPERATION=%lu AV_ADDRESS=0x%08lX\n",
               (unsigned long)ep->ExceptionRecord->ExceptionInformation[0],
               (unsigned long)ep->ExceptionRecord->ExceptionInformation[1]);
    }
#if defined(_M_IX86)
    printf("EIP=0x%08lX ESP=0x%08lX EBP=0x%08lX EAX=0x%08lX EBX=0x%08lX ECX=0x%08lX EDX=0x%08lX ESI=0x%08lX EDI=0x%08lX\n",
           (unsigned long)ep->ContextRecord->Eip,
           (unsigned long)ep->ContextRecord->Esp,
           (unsigned long)ep->ContextRecord->Ebp,
           (unsigned long)ep->ContextRecord->Eax,
           (unsigned long)ep->ContextRecord->Ebx,
           (unsigned long)ep->ContextRecord->Ecx,
           (unsigned long)ep->ContextRecord->Edx,
           (unsigned long)ep->ContextRecord->Esi,
           (unsigned long)ep->ContextRecord->Edi);
#endif
    fflush(stdout);
    return EXCEPTION_EXECUTE_HANDLER;
}

int main(int argc, char **argv)
{
    static unsigned char lic[34] = {
        6,0,0,0,171,16,21,14,16,26,84,22,23,21,22,157,31,
        29,15,229,88,92,94,96,96,100,102,111,56,26,95,75,182,33
    };
    unsigned char box[128];
    char *product = (char *)box + 16;
    const char *dll_name;
    int which;
    PFN_INIT init;
    PFN_FINI fini;
    char *p_arg;
    void *l_arg;
    int rc = -999;
    int i;

    if (argc != 3) {
        fprintf(stderr, "usage: %s <dll> <case 0..3>\n", argv[0]);
        return 2;
    }
    dll_name = argv[1];
    which = atoi(argv[2]);
    if (which < 0 || which > 3) return 3;
    for (i = 0; i < (int)sizeof(box); ++i) box[i] = 0xA5;

    g_module = LoadLibraryA(dll_name);
    if (!g_module) {
        printf("CASE=%d LOAD_FAIL ERROR=%lu\n", which, (unsigned long)GetLastError());
        return 10;
    }
    init = (PFN_INIT)GetProcAddress(g_module, "_SigProc_Init@8");
    fini = (PFN_FINI)GetProcAddress(g_module, "_SigProc_Fini@0");
    if (!init || !fini) {
        printf("CASE=%d EXPORT_FAIL ERROR=%lu\n", which, (unsigned long)GetLastError());
        FreeLibrary(g_module);
        return 11;
    }

    p_arg = (which & 1) ? product : NULL;
    l_arg = (which & 2) ? (void *)lic : NULL;
    printf("CASE=%d BEGIN PRODUCT=%s LICENSE=%s MODULE=0x%08lX\n",
           which, p_arg ? "WRITEABLE" : "NULL", l_arg ? "REAL" : "NULL",
           (unsigned long)(uintptr_t)g_module);
    fflush(stdout);

    __try {
        rc = init(p_arg, l_arg);
        printf("CASE=%d INIT_RETURN=%d", which, rc);
        if (p_arg) printf(" PRODUCT=%s", p_arg);
        printf("\n");
        fflush(stdout);
        if (rc) {
            fini();
            printf("CASE=%d FINI_RETURNED\n", which);
            fflush(stdout);
        }
    }
    __except(report_exception(GetExceptionInformation(), which)) {
        FreeLibrary(g_module);
        return 100 + which;
    }

    if (!FreeLibrary(g_module)) {
        printf("CASE=%d FREE_FAIL ERROR=%lu\n", which, (unsigned long)GetLastError());
        return 20;
    }
    printf("CASE=%d COMPLETE\n", which);
    return 0;
}
