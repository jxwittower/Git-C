#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct Sample4 { int16_t lane[4]; } Sample4;
typedef uint32_t (__stdcall *PFN_SIGPROC)(const uint32_t*, const Sample4*, int, void*, void*, void*);
typedef int (__stdcall *PFN_INIT)(char*, void*);
typedef unsigned char (__stdcall *PFN_STAT)(void);
typedef void (__stdcall *PFN_FINI)(void);

static unsigned char lic[34]={6,0,0,0,171,16,21,14,16,26,84,22,23,21,22,157,31,29,15,229,88,92,94,96,96,100,102,111,56,26,95,75,182,33};

static int read_frame(FILE *fp, uint32_t **ids, Sample4 **samples, int *count) {
    uint32_t n; uint16_t tl; char *ts;
    if (fread(&n,4,1,fp)!=1) return 0;
    if (fread(&tl,2,1,fp)!=1) return -1;
    if (n > 100000 || tl > 4096) return -2;
    ts=(char*)malloc((size_t)tl+1); *ids=(uint32_t*)malloc((size_t)n*4); *samples=(Sample4*)malloc((size_t)n*sizeof(Sample4));
    if(!ts||!*ids||!*samples) return -3;
    if(fread(ts,1,tl,fp)!=tl || fread(*ids,4,n,fp)!=n || fread(*samples,sizeof(Sample4),n,fp)!=n) return -4;
    ts[tl]=0; free(ts); *count=(int)n; return 1;
}

int main(int argc,char **argv){
    HMODULE h; PFN_INIT init; PFN_SIGPROC proc; PFN_STAT stat; PFN_FINI fini;
    FILE *fp; unsigned char state[0x105c], result[0x786]; char product[80]; int rc,frame=0;
    if(argc!=3){fprintf(stderr,"usage: native_nonzero_smoke.exe runtime_dir ghf\n");return 2;}
    if(!SetCurrentDirectoryA(argv[1])){fprintf(stderr,"chdir fail %lu\n",GetLastError());return 3;}
    h=LoadLibraryA("..\\SigProcDll-64HF.dll"); if(!h){fprintf(stderr,"load fail %lu\n",GetLastError());return 4;}
    init=(PFN_INIT)GetProcAddress(h,"_SigProc_Init@8"); proc=(PFN_SIGPROC)GetProcAddress(h,"_SigProc@24"); stat=(PFN_STAT)GetProcAddress(h,"_SigProc_Stat@0"); fini=(PFN_FINI)GetProcAddress(h,"_SigProc_Fini@0");
    if(!init||!proc||!stat||!fini){fprintf(stderr,"exports fail\n");return 5;}
    memset(product,0,sizeof(product)); rc=init(product,lic); if(!rc){fprintf(stderr,"init fail\n");return 6;}
    fp=fopen(argv[2],"rb"); if(!fp){fprintf(stderr,"open ghf fail\n");return 7;}
    for(;;){
        uint32_t *ids=0, seq; Sample4 *samples=0; int n=0; int rr=read_frame(fp,&ids,&samples,&n);
        if(rr==0) break; if(rr<0){fprintf(stderr,"frame parse fail %d\n",rr);return 8;}
        memset(state,0,sizeof(state)); memset(result,0,sizeof(result));
        seq=proc(ids,samples,n,0,state,result);
        free(ids); free(samples); frame++;
        if(seq==0 || stat()!=1){fprintf(stderr,"proc contract fail frame=%d seq=%u stat=%u\n",frame,(unsigned)seq,(unsigned)stat());return 9;}
        if(frame==1 || frame%25==0) printf("FRAME_OK=%d seq=%u state=%u hr=%u rr=%u\n",frame,(unsigned)seq,(unsigned)state[0x404],(unsigned)(state[2]|((unsigned)state[3]<<8)),(unsigned)(state[0]|((unsigned)state[1]<<8)));
    }
    fclose(fp); fini(); if(stat()!=0){fprintf(stderr,"fini stat fail\n");return 10;} FreeLibrary(h);
    printf("NONZERO_NATIVE_SMOKE_PASS frames=%d\n",frame); return frame>0?0:11;
}
