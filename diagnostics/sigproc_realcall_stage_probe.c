#define _CRT_SECURE_NO_WARNINGS
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define STATE_BYTES 0x105c
#define RESULT_BYTES 0x786
#define STATE_MAIN 0x404

typedef struct { int16_t lane[4]; } Sample4;
typedef uint32_t (__stdcall *PFN_PROC)(const uint32_t*, const void*, int, void*, void*, void*);
typedef int (__stdcall *PFN_INIT)(char*, void*);
typedef unsigned char (__stdcall *PFN_STAT)(void);
typedef void (__stdcall *PFN_FINI)(void);
typedef struct { uint32_t n; uint32_t *ids; Sample4 *s; } Frame;

static const unsigned char LICENSE_BLOB[34]={6,0,0,0,171,16,21,14,16,26,84,22,23,21,22,157,31,29,15,229,88,92,94,96,96,100,102,111,56,26,95,75,182,33};

static uint16_t rd16(const unsigned char *p, size_t o){ return (uint16_t)(p[o] | ((uint16_t)p[o+1]<<8)); }
static void joinp(char *out,size_t cap,const char *a,const char *b){ size_t n=strlen(a); snprintf(out,cap,"%s%s%s",a,(n&&a[n-1]!='\\'&&a[n-1]!='/')?"\\":"",b); }
static int copy_runtime(const char *templ,const char *work){
    static const char *files[]={"file_bed_model_v1","file_sig","filter_hrt3","filter_brth","file_bias"};
    char a[MAX_PATH*4],b[MAX_PATH*4]; int i;
    if(!CreateDirectoryA(work,NULL) && GetLastError()!=ERROR_ALREADY_EXISTS) return 0;
    for(i=0;i<5;i++){
        joinp(a,sizeof(a),templ,files[i]); joinp(b,sizeof(b),work,files[i]);
        if(GetFileAttributesA(a)!=INVALID_FILE_ATTRIBUTES && !CopyFileA(a,b,FALSE)) return 0;
    }
    return 1;
}
static int read_frame(FILE *f,Frame *fr){
    uint16_t tl; char *ts;
    memset(fr,0,sizeof(*fr));
    if(fread(&fr->n,4,1,f)!=1) return feof(f)?0:-1;
    if(fread(&tl,2,1,f)!=1) return -1;
    if(tl>4096 || fr->n>2000000u) return -1;
    ts=(char*)malloc((size_t)tl+1); fr->ids=(uint32_t*)malloc((size_t)fr->n*4); fr->s=(Sample4*)malloc((size_t)fr->n*sizeof(Sample4));
    if(!ts||!fr->ids||!fr->s){ free(ts); free(fr->ids); free(fr->s); memset(fr,0,sizeof(*fr)); return -1; }
    if(fread(ts,1,tl,f)!=tl || fread(fr->ids,4,fr->n,f)!=fr->n || fread(fr->s,sizeof(Sample4),fr->n,f)!=fr->n){ free(ts); free(fr->ids); free(fr->s); memset(fr,0,sizeof(*fr)); return -1; }
    free(ts); return 1;
}
static void free_frame(Frame *fr){ free(fr->ids); free(fr->s); memset(fr,0,sizeof(*fr)); }

int main(int argc,char **argv){
    char dll[MAX_PATH*4],runtime[MAX_PATH*4],ghf[MAX_PATH*4],cwd[MAX_PATH*4],work[MAX_PATH*4],product[128];
    HMODULE h=NULL; PFN_PROC proc=NULL; PFN_INIT init=NULL; PFN_STAT stat=NULL; PFN_FINI fini=NULL;
    FILE *f=NULL; Frame fr; int calls,i,j,ok=0; DWORD n;
    setvbuf(stdout,NULL,_IONBF,0); setvbuf(stderr,NULL,_IONBF,0);
    memset(&fr,0,sizeof(fr));
    if(argc!=5){ fprintf(stderr,"usage: %s <dll> <runtime> <ghf> <calls>\n",argv[0]); return 2; }
    calls=atoi(argv[4]); if(calls<1||calls>100000) return 3;
    n=GetFullPathNameA(argv[1],sizeof(dll),dll,NULL); if(!n||n>=sizeof(dll)) return 4;
    n=GetFullPathNameA(argv[2],sizeof(runtime),runtime,NULL); if(!n||n>=sizeof(runtime)) return 5;
    n=GetFullPathNameA(argv[3],sizeof(ghf),ghf,NULL); if(!n||n>=sizeof(ghf)) return 6;
    if(!GetCurrentDirectoryA(sizeof(cwd),cwd)) return 7;
    snprintf(work,sizeof(work),"%s\\realprobe_%lu",cwd,(unsigned long)GetCurrentProcessId());
    printf("STAGE=BEGIN DLL=%s RUNTIME=%s GHF=%s CALLS=%d\n",dll,runtime,ghf,calls);
    if(!copy_runtime(runtime,work)){ printf("STAGE=RUNTIME_COPY_FAIL ERR=%lu\n",(unsigned long)GetLastError()); return 10; }
    printf("STAGE=RUNTIME_COPY_PASS WORK=%s\n",work);
    f=fopen(ghf,"rb"); if(!f){ printf("STAGE=GHF_OPEN_FAIL\n"); return 11; }
    if(read_frame(f,&fr)!=1){ printf("STAGE=GHF_FIRST_FRAME_FAIL\n"); fclose(f); return 12; }
    fclose(f); f=NULL;
    printf("STAGE=GHF_FIRST_FRAME_PASS N=%lu\n",(unsigned long)fr.n);
    if(!SetCurrentDirectoryA(work)){ printf("STAGE=CHDIR_FAIL ERR=%lu\n",(unsigned long)GetLastError()); free_frame(&fr); return 13; }
    printf("STAGE=LOADLIB_BEGIN\n");
    h=LoadLibraryA(dll); if(!h){ printf("STAGE=LOADLIB_FAIL ERR=%lu\n",(unsigned long)GetLastError()); goto done; }
    printf("STAGE=LOADLIB_PASS MODULE=0x%08lX\n",(unsigned long)(uintptr_t)h);
    proc=(PFN_PROC)GetProcAddress(h,"_SigProc@24"); init=(PFN_INIT)GetProcAddress(h,"_SigProc_Init@8"); stat=(PFN_STAT)GetProcAddress(h,"_SigProc_Stat@0"); fini=(PFN_FINI)GetProcAddress(h,"_SigProc_Fini@0");
    if(!proc||!init||!stat||!fini){ printf("STAGE=EXPORT_FAIL ERR=%lu\n",(unsigned long)GetLastError()); goto done; }
    printf("STAGE=EXPORT_PASS\n");
    memset(product,0,sizeof(product));
    printf("STAGE=INIT_BEGIN\n");
    i=init(product,(void*)LICENSE_BLOB);
    printf("STAGE=INIT_RETURN RC=%d PRODUCT=%s\n",i,product);
    if(!i) goto done;
    printf("STAGE=STAT_AFTER_INIT VALUE=%u\n",(unsigned)stat());
    for(i=0;i<calls;i++){
        unsigned char sb[STATE_BYTES+32],rb[RESULT_BYTES+32]; unsigned char *st=sb+16,*res=rb+16; uint32_t seq; int guard_ok=1;
        memset(sb,0xa5,sizeof(sb)); memset(rb,0x5a,sizeof(rb));
        printf("STAGE=CALL_BEGIN I=%d N=%lu\n",i,(unsigned long)fr.n);
        seq=proc(fr.ids,fr.s,(int)fr.n,NULL,st,res);
        printf("STAGE=CALL_RETURN I=%d SEQ=%lu MAIN=%u HR=%u BR=%u\n",i,(unsigned long)seq,(unsigned)st[STATE_MAIN],(unsigned)rd16(st,2),(unsigned)rd16(st,0));
        for(j=0;j<16;j++) if(sb[j]!=0xa5||sb[STATE_BYTES+16+j]!=0xa5||rb[j]!=0x5a||rb[RESULT_BYTES+16+j]!=0x5a){guard_ok=0;break;}
        if(!seq || !guard_ok){ printf("STAGE=CALL_CONTRACT_FAIL I=%d SEQ=%lu GUARD=%d\n",i,(unsigned long)seq,guard_ok); goto done; }
    }
    printf("STAGE=STAT_BEFORE_FINI VALUE=%u\n",(unsigned)stat());
    printf("STAGE=FINI_BEGIN\n"); fini(); printf("STAGE=FINI_RETURN STAT=%u\n",(unsigned)stat());
    fini=NULL; ok=1;
 done:
    if(fini){ printf("STAGE=CLEANUP_FINI_BEGIN\n"); fini(); printf("STAGE=CLEANUP_FINI_RETURN\n"); }
    if(h){ FreeLibrary(h); printf("STAGE=FREELIB_RETURN\n"); }
    SetCurrentDirectoryA(cwd); free_frame(&fr);
    if(ok){ printf("REALCALL_STAGE_PROBE_PASS CALLS=%d\n",calls); return 0; }
    printf("REALCALL_STAGE_PROBE_FAIL\n"); return 20;
}
