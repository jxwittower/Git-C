#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>

/* Public ABI remains exactly the existing 32-bit stdcall contract. */
typedef struct Sample4 { int16_t lane[4]; } Sample4;
typedef uint32_t (__stdcall *PFN_SIGPROC)(const uint32_t*,const Sample4*,int,void*,void*,void*);
typedef int (__stdcall *PFN_INIT)(char*,void*);
typedef unsigned char (__stdcall *PFN_STAT)(void);
typedef void (__stdcall *PFN_FINI)(void);

enum { EMPTY_RANGE_SUM_THRESHOLD = 300, EMPTY_CONFIRM_FRAMES = 3 };

static HMODULE g_self = NULL;
static HMODULE g_core = NULL;
static PFN_SIGPROC g_proc = NULL;
static PFN_INIT g_init = NULL;
static PFN_STAT g_stat = NULL;
static PFN_FINI g_fini = NULL;
static volatile LONG g_lock = 0;
static unsigned int g_low_frames = 0;

static void lock_enter(void) {
    while (InterlockedCompareExchange(&g_lock, 1, 0) != 0) Sleep(0);
}
static void lock_leave(void) { InterlockedExchange(&g_lock, 0); }

static int core_path(char *out, DWORD cap) {
    DWORD n, i, slash = 0;
    if (!out || cap < 32 || !g_self) return 0;
    n = GetModuleFileNameA(g_self, out, cap);
    if (!n || n >= cap) return 0;
    for (i = 0; i < n; ++i) if (out[i] == '\\' || out[i] == '/') slash = i + 1;
    /* Keep the wrapper basename and append .core.dll, e.g.
       SigProcDll-64HF.dll -> SigProcDll-64HF.core.dll.
       This also gives independent cores to a.dll / b.dll in the 2-thread gate. */
    for (i = slash; i < n; ++i) {
        if (out[i] == '.') { n = i; break; }
    }
    if (n + 9 >= cap) return 0;
    out[n++]='.'; out[n++]='c'; out[n++]='o'; out[n++]='r'; out[n++]='e';
    out[n++]='.'; out[n++]='d'; out[n++]='l'; out[n++]='l'; out[n]=0;
    return 1;
}

static int load_core(void) {
    char path[MAX_PATH * 2];
    if (g_core) return 1;
    if (!core_path(path, (DWORD)sizeof(path))) return 0;
    g_core = LoadLibraryA(path);
    if (!g_core) return 0;
    g_init = (PFN_INIT)GetProcAddress(g_core, "_SigProc_Init@8");
    g_proc = (PFN_SIGPROC)GetProcAddress(g_core, "_SigProc@24");
    g_stat = (PFN_STAT)GetProcAddress(g_core, "_SigProc_Stat@0");
    g_fini = (PFN_FINI)GetProcAddress(g_core, "_SigProc_Fini@0");
    if (!g_init || !g_proc || !g_stat || !g_fini) {
        FreeLibrary(g_core); g_core = NULL; g_init = NULL; g_proc = NULL; g_stat = NULL; g_fini = NULL;
        return 0;
    }
    return 1;
}

static unsigned int range_sum4(const Sample4 *s, int n) {
    int16_t mn[4], mx[4];
    int i, j;
    unsigned int total = 0;
    if (!s || n <= 0) return 0xffffffffu;
    for (j=0;j<4;++j) mn[j]=mx[j]=s[0].lane[j];
    for (i=1;i<n;++i) {
        for (j=0;j<4;++j) {
            int16_t v=s[i].lane[j];
            if (v<mn[j]) mn[j]=v;
            if (v>mx[j]) mx[j]=v;
        }
    }
    for (j=0;j<4;++j) total += (unsigned int)((int)mx[j] - (int)mn[j]);
    return total;
}

__declspec(dllexport) int __stdcall SigProc_Init(char *product, void *lic) {
    int rc = 0;
    lock_enter();
    g_low_frames = 0;
    if (load_core()) rc = g_init(product, lic);
    lock_leave();
    return rc;
}

__declspec(dllexport) uint32_t __stdcall SigProc(const uint32_t *ids,const Sample4 *samples,int n,void *arg4,void *state,void *result) {
    uint32_t seq = 0;
    unsigned int metric;
    unsigned char *st = (unsigned char*)state;
    lock_enter();
    if (load_core()) {
        seq = g_proc(ids, samples, n, arg4, state, result);
        metric = range_sum4(samples, n);
        if (metric < EMPTY_RANGE_SUM_THRESHOLD) {
            if (g_low_frames < 0xffffffffu) ++g_low_frames;
        } else {
            g_low_frames = 0;
        }
        /* Objective low-noise empty-bed confirmation. The core's occupied/leave/recovery
           semantics remain untouched above the empirically clean 300-count boundary. */
        if (st && g_low_frames >= EMPTY_CONFIRM_FRAMES) {
            st[0] = 0; st[1] = 0; /* RR */
            st[2] = 0; st[3] = 0; /* HR */
            st[0x404] = 0;        /* mattress/occupancy state */
        }
    }
    lock_leave();
    return seq;
}

__declspec(dllexport) unsigned char __stdcall SigProc_Stat(void) {
    unsigned char s = 0;
    lock_enter();
    if (g_core && g_stat) s = g_stat();
    lock_leave();
    return s;
}

__declspec(dllexport) void __stdcall SigProc_Fini(void) {
    HMODULE h = NULL;
    lock_enter();
    if (g_core && g_fini) g_fini();
    h = g_core;
    g_core = NULL; g_init = NULL; g_proc = NULL; g_stat = NULL; g_fini = NULL; g_low_frames = 0;
    lock_leave();
    if (h) FreeLibrary(h);
}

BOOL WINAPI DllMain(HINSTANCE hinst, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) { g_self = (HMODULE)hinst; DisableThreadLibraryCalls(hinst); }
    return TRUE;
}
