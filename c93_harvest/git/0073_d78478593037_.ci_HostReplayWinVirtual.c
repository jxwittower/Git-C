#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define STATE_BYTES 0x105c
#define RESULT_BYTES 0x786
#define MAX_GHFS 32

typedef struct Sample4 { int16_t lane[4]; } Sample4;
typedef uint32_t (__stdcall *PFN_PROC)(const uint32_t*, const void*, int, void*, void*, void*);
typedef int (__stdcall *PFN_INIT)(char*, void*);
typedef unsigned char (__stdcall *PFN_STAT)(void);
typedef void (__stdcall *PFN_FINI)(void);

typedef struct Api {
    HMODULE mod; PFN_PROC proc; PFN_INIT init; PFN_STAT stat; PFN_FINI fini;
} Api;

typedef struct Frame {
    uint32_t n; uint32_t *ids; Sample4 *samples;
} Frame;

typedef struct StressCtx {
    PFN_PROC proc; const Frame *frame; int loops; volatile LONG *failures;
} StressCtx;

static int g_virtual_1hz = 0;
static LONGLONG g_virtual_ticks = 0;

static BOOL WINAPI virtual_QueryPerformanceFrequency(LARGE_INTEGER *v) {
    if (!v) return FALSE;
    v->QuadPart = 1000000LL;
    return TRUE;
}
static BOOL WINAPI virtual_QueryPerformanceCounter(LARGE_INTEGER *v) {
    if (!v) return FALSE;
    g_virtual_ticks += 1000000LL;
    v->QuadPart = g_virtual_ticks;
    return TRUE;
}
static int patch_iat_import(HMODULE mod, const char *dll_name, const char *func_name, FARPROC replacement) {
    BYTE *base=(BYTE*)mod;
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS32 *nt;
    IMAGE_IMPORT_DESCRIPTOR *imp;
    DWORD rva;
    if(!base) return 0;
    dos=(IMAGE_DOS_HEADER*)base;
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE) return 0;
    nt=(IMAGE_NT_HEADERS32*)(base+dos->e_lfanew);
    if(nt->Signature!=IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC) return 0;
    rva=nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress;
    if(!rva) return 0;
    imp=(IMAGE_IMPORT_DESCRIPTOR*)(base+rva);
    for(;imp->Name;imp++){
        const char *name=(const char*)(base+imp->Name);
        IMAGE_THUNK_DATA32 *orig,*iat;
        if(_stricmp(name,dll_name)!=0) continue;
        if(!imp->OriginalFirstThunk) return 0;
        orig=(IMAGE_THUNK_DATA32*)(base+imp->OriginalFirstThunk);
        iat=(IMAGE_THUNK_DATA32*)(base+imp->FirstThunk);
        for(;orig->u1.AddressOfData;orig++,iat++){
            IMAGE_IMPORT_BY_NAME *ibn;
            DWORD oldprot;
            if(IMAGE_SNAP_BY_ORDINAL32(orig->u1.Ordinal)) continue;
            ibn=(IMAGE_IMPORT_BY_NAME*)(base+orig->u1.AddressOfData);
            if(strcmp((const char*)ibn->Name,func_name)!=0) continue;
            if(!VirtualProtect(&iat->u1.Function,sizeof(iat->u1.Function),PAGE_READWRITE,&oldprot)) return 0;
            iat->u1.Function=(DWORD)(ULONG_PTR)replacement;
            {
                DWORD ignored;
                if(!VirtualProtect(&iat->u1.Function,sizeof(iat->u1.Function),oldprot,&ignored)) return 0;
            }
            return 1;
        }
    }
    return 0;
}
static int install_virtual_1hz_clock(HMODULE mod) {
    int a,b;
    g_virtual_ticks=0;
    a=patch_iat_import(mod,"KERNEL32.dll","QueryPerformanceCounter",(FARPROC)virtual_QueryPerformanceCounter);
    b=patch_iat_import(mod,"KERNEL32.dll","QueryPerformanceFrequency",(FARPROC)virtual_QueryPerformanceFrequency);
    if(!a||!b){fprintf(stderr,"VIRTUAL_CLOCK_PATCH_FAIL qpc=%d qpf=%d\n",a,b);return 0;}
    fprintf(stderr,"VIRTUAL_CLOCK_1HZ_IAT_PATCH_PASS\n");
    return 1;
}

static const unsigned char k_license[34] = {
    6,0,0,0,171,16,21,14,16,26,84,22,23,21,22,157,31,29,15,229,88,92,94,96,96,100,102,111,56,26,95,75,182,33
};

static uint16_t rd16(const unsigned char *p, size_t o) {
    return (uint16_t)((uint16_t)p[o] | ((uint16_t)p[o+1] << 8));
}
static uint64_t fnv1a64(const void *vp, size_t n) {
    const unsigned char *p=(const unsigned char*)vp; uint64_t h=1469598103934665603ULL; size_t i;
    for(i=0;i<n;i++){ h ^= (uint64_t)p[i]; h *= 1099511628211ULL; }
    return h;
}
static double qpc_ms(LARGE_INTEGER a, LARGE_INTEGER b, LARGE_INTEGER f) {
    return 1000.0 * (double)(b.QuadPart-a.QuadPart)/(double)f.QuadPart;
}
static int api_load(Api *a, const char *dll) {
    memset(a,0,sizeof(*a));
    a->mod=LoadLibraryA(dll); if(!a->mod){fprintf(stderr,"LOAD_FAIL error=%lu dll=%s\n",GetLastError(),dll);return 0;}
    a->init=(PFN_INIT)GetProcAddress(a->mod,"_SigProc_Init@8");
    a->proc=(PFN_PROC)GetProcAddress(a->mod,"_SigProc@24");
    a->stat=(PFN_STAT)GetProcAddress(a->mod,"_SigProc_Stat@0");
    a->fini=(PFN_FINI)GetProcAddress(a->mod,"_SigProc_Fini@0");
    if(!a->init||!a->proc||!a->stat||!a->fini){fprintf(stderr,"EXPORT_FAIL\n");FreeLibrary(a->mod);memset(a,0,sizeof(*a));return 0;}
    if(g_virtual_1hz && !install_virtual_1hz_clock(a->mod)){FreeLibrary(a->mod);memset(a,0,sizeof(*a));return 0;}
    return 1;
}
static void api_unload(Api *a){ if(a->mod){FreeLibrary(a->mod);} memset(a,0,sizeof(*a)); }
static int api_init(Api *a) {
    char product[128]; int rc; memset(product,0,sizeof(product));
    rc=a->init(product,(void*)k_license);
    if(!rc){fprintf(stderr,"INIT_FAIL\n");return 0;}
    if(a->stat()!=1){fprintf(stderr,"STAT_NOT_READY_AFTER_INIT\n");return 0;}
    fprintf(stderr,"PRODUCT=%s\n",product);
    return 1;
}
static int read_frame(FILE *f, Frame *fr) {
    uint32_t n; uint16_t tl; char *ts;
    memset(fr,0,sizeof(*fr));
    if(fread(&n,4,1,f)!=1) return 0;
    if(fread(&tl,2,1,f)!=1) return -1;
    if(n==0 || n>1000000U || tl>4096U) return -1;
    ts=(char*)malloc((size_t)tl); if(!ts) return -1;
    if(tl && fread(ts,1,tl,f)!=tl){free(ts);return -1;} free(ts);
    fr->ids=(uint32_t*)malloc((size_t)n*sizeof(uint32_t));
    fr->samples=(Sample4*)malloc((size_t)n*sizeof(Sample4));
    if(!fr->ids||!fr->samples){free(fr->ids);free(fr->samples);memset(fr,0,sizeof(*fr));return -1;}
    fr->n=n;
    if(fread(fr->ids,sizeof(uint32_t),n,f)!=n || fread(fr->samples,sizeof(Sample4),n,f)!=n){free(fr->ids);free(fr->samples);memset(fr,0,sizeof(*fr));return -1;}
    return 1;
}
static void free_frame(Frame *fr){ free(fr->ids);free(fr->samples);memset(fr,0,sizeof(*fr)); }
static int load_first_frame(const char *path, Frame *fr){ FILE *f=fopen(path,"rb");int r;if(!f){fprintf(stderr,"OPEN_GHF_FAIL %s\n",path);return 0;}r=read_frame(f,fr);fclose(f);return r==1; }

static DWORD WINAPI stress_thread(LPVOID pv) {
    StressCtx *c=(StressCtx*)pv; unsigned char *state,*result; int i;
    state=(unsigned char*)malloc(STATE_BYTES); result=(unsigned char*)malloc(RESULT_BYTES);
    if(!state||!result){InterlockedIncrement(c->failures);free(state);free(result);return 1;}
    for(i=0;i<c->loops;i++){
        uint32_t seq;
        memset(state,0,STATE_BYTES); memset(result,0,RESULT_BYTES);
        seq=c->proc(c->frame->ids,c->frame->samples,(int)c->frame->n,NULL,state,result);
        if(seq==0){InterlockedIncrement(c->failures);break;}
    }
    free(state); free(result); return 0;
}

static int run_stress(const char *dll, const char *ghf, int loops, int threads) {
    Api a; Frame fr; HANDLE *hs; StressCtx *ctxs; volatile LONG failures=0; int i,ok=0;
    if(threads<1||threads>32||loops<1)return 2;
    if(!load_first_frame(ghf,&fr))return 3;
    if(!api_load(&a,dll)){free_frame(&fr);return 4;}
    if(!api_init(&a)){api_unload(&a);free_frame(&fr);return 5;}
    hs=(HANDLE*)calloc((size_t)threads,sizeof(HANDLE));ctxs=(StressCtx*)calloc((size_t)threads,sizeof(StressCtx));
    if(!hs||!ctxs)goto done;
    for(i=0;i<threads;i++){
        ctxs[i].proc=a.proc;ctxs[i].frame=&fr;ctxs[i].loops=loops;ctxs[i].failures=&failures;
        hs[i]=CreateThread(NULL,0,stress_thread,&ctxs[i],0,NULL); if(!hs[i]){InterlockedIncrement(&failures);break;}
    }
    if(i>0)WaitForMultipleObjects((DWORD)i,hs,TRUE,INFINITE);
    while(i>0){i--;if(hs[i])CloseHandle(hs[i]);}
    if(failures==0 && a.stat()==1){
        printf("STRESS_PASS threads=%d loops_each=%d total_calls=%d\n",threads,loops,threads*loops);ok=1;
    } else fprintf(stderr,"STRESS_FAIL failures=%ld stat=%u\n",failures,(unsigned)a.stat());
done:
    a.fini(); if(a.stat()!=0){fprintf(stderr,"STAT_AFTER_FINI_FAIL\n");ok=0;} api_unload(&a);free_frame(&fr);free(hs);free(ctxs);return ok?0:6;
}

static int run_replay(const char *dll, char **ghfs, int nghf, int sleep_ms, const char *outpath, int sequence_sentinel, int max_frames) {
    Api a; FILE *out=NULL; unsigned char *state=NULL,*result=NULL; int gi; unsigned long long row=0; int ok=0;
    uint64_t combined=1469598103934665603ULL; unsigned state8=0,state8_bad_vital=0,recovered_after8=0,vitals_after8=0,zero_after8=0;
    LARGE_INTEGER fq,t0,t1; double total_ms=0.0,max_ms=0.0;
    if(!api_load(&a,dll))return 10; if(!api_init(&a)){api_unload(&a);return 11;}
    state=(unsigned char*)malloc(STATE_BYTES);result=(unsigned char*)malloc(RESULT_BYTES);if(!state||!result)goto done;
    if(outpath){out=fopen(outpath,"wb");if(!out)goto done;fprintf(out,"row,source,seq,state,hr,rr,hstat,rstat,state_hash,result_hash\r\n");}
    QueryPerformanceFrequency(&fq);
    for(gi=0;gi<nghf;gi++){
        FILE *f=fopen(ghfs[gi],"rb"); if(!f){fprintf(stderr,"OPEN_GHF_FAIL %s\n",ghfs[gi]);goto done;}
        for(;;){
            Frame fr;int rr=read_frame(f,&fr);uint32_t seq;unsigned st,hr,resp,hstat,rstat;uint64_t sh,rh;double ms;
            if(rr==0)break;if(rr<0){fclose(f);fprintf(stderr,"GHF_PARSE_FAIL %s\n",ghfs[gi]);goto done;}
            memset(state,0,STATE_BYTES);memset(result,0,RESULT_BYTES);
            QueryPerformanceCounter(&t0);seq=a.proc(fr.ids,fr.samples,(int)fr.n,NULL,state,result);QueryPerformanceCounter(&t1);
            free_frame(&fr);if(seq==0){fclose(f);fprintf(stderr,"PROC_RETURNED_ZERO row=%llu\n",row);goto done;}
            ms=qpc_ms(t0,t1,fq);total_ms+=ms;if(ms>max_ms)max_ms=ms;
            st=(unsigned)state[0x404];hr=(unsigned)rd16(state,2);resp=(unsigned)rd16(state,0);hstat=(unsigned)state[0xeb8];rstat=(unsigned)state[0xeaa];
            sh=fnv1a64(state,STATE_BYTES);rh=fnv1a64(result,RESULT_BYTES);combined^=sh;combined*=1099511628211ULL;combined^=rh;combined*=1099511628211ULL;
            if(out)fprintf(out,"%llu,%d,%lu,%u,%u,%u,%u,%u,%016llx,%016llx\r\n",row,gi,(unsigned long)seq,st,hr,resp,hstat,rstat,(unsigned long long)sh,(unsigned long long)rh);
            if(st==8){state8++;if(hr!=0||resp!=0)state8_bad_vital++;}
            if(state8>0 && st==0)zero_after8=1;
            if(state8>0 && st!=8){recovered_after8=1;if(hr>0||resp>0)vitals_after8=1;}
            row++;
            if(sleep_ms>0)Sleep((DWORD)sleep_ms);
            if(max_frames>0 && (int)row>=max_frames){break;}
        }
        fclose(f);if(max_frames>0 && (int)row>=max_frames)break;
    }
    if(a.stat()!=1){fprintf(stderr,"STAT_DROPPED_DURING_REPLAY\n");goto done;}
    printf("REPLAY_PASS frames=%llu files=%d total_ms=%.3f max_call_ms=%.3f digest=%016llx\n",row,nghf,total_ms,max_ms,(unsigned long long)combined);
    if(sequence_sentinel){
        printf("SEQ_COUNTS state8=%u bad_vital=%u recovered=%u vitals_after=%u zero_after=%u\n",state8,state8_bad_vital,recovered_after8,vitals_after8,zero_after8);
        if(state8==0 || state8_bad_vital!=0 || !recovered_after8 || !vitals_after8 || !zero_after8){fprintf(stderr,"SEQ_SENTINEL_FAIL\n");goto done;}
        printf("SEQ_TARGETS_VITAL_SUPPRESSION_RECOVERY_PASS\n");
    }
    ok=1;
done:
    if(out)fclose(out); if(a.mod){a.fini();if(a.stat()!=0){fprintf(stderr,"STAT_AFTER_FINI_FAIL\n");ok=0;}}api_unload(&a);free(state);free(result);return ok?0:12;
}

static void usage(void){
    fprintf(stderr,"HostReplayWin --dll DLL --mode replay|stress --ghf FILE [--ghf FILE...] [--out FILE] [--sleep-ms N] [--loops N] [--threads N] [--sequence-sentinel] [--max-frames N] [--virtual-1hz]\n");
}
int main(int argc,char **argv){
    const char *dll=NULL,*mode=NULL,*out=NULL;char *ghfs[MAX_GHFS];int nghf=0,sleep_ms=0,loops=2000,threads=2,seqsent=0,max_frames=0,i;
    for(i=1;i<argc;i++){
        if(!strcmp(argv[i],"--dll")&&i+1<argc)dll=argv[++i];
        else if(!strcmp(argv[i],"--mode")&&i+1<argc)mode=argv[++i];
        else if(!strcmp(argv[i],"--ghf")&&i+1<argc&&nghf<MAX_GHFS)ghfs[nghf++]=argv[++i];
        else if(!strcmp(argv[i],"--out")&&i+1<argc)out=argv[++i];
        else if(!strcmp(argv[i],"--sleep-ms")&&i+1<argc)sleep_ms=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--loops")&&i+1<argc)loops=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--threads")&&i+1<argc)threads=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--sequence-sentinel"))seqsent=1;
        else if(!strcmp(argv[i],"--max-frames")&&i+1<argc)max_frames=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--virtual-1hz"))g_virtual_1hz=1;
        else {usage();return 2;}
    }
    if(!dll||!mode||nghf<1){usage();return 2;}
    if(!strcmp(mode,"stress"))return run_stress(dll,ghfs[0],loops,threads);
    if(!strcmp(mode,"replay"))return run_replay(dll,ghfs,nghf,sleep_ms,out,seqsent,max_frames);
    usage();return 2;
}
