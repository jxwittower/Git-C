from pathlib import Path
import struct,hashlib,sys

HOST_SHA='081c4c62d2bf377913eb2aca0cc3cf3bf656350c8abaa3aaf11d171dac604804'
HOSTFIX_SHA='ba15a5b0d4755597892ab6d20b0f9eeb49d5ac5da9dfd97ed6e94ecff7aac13b'
HARNESS_IN='90bd3ef14c9948677f259641e15227a7d26481baf399ae61ef67d09b031ecf71'
HARNESS_OUT='f068bfa856ad791e0e8663cd4d76f54dc64f1b5e61fffb7a7fc02b4ff7b21582'
RUNNER_OUT='c46f453d61438b12b2198c3c0d43d81f2274aea4815a96a94519c08408a5bb11'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def crlf_bytes(s): return s.replace('\r\n','\n').replace('\r','\n').replace('\n','\r\n').encode('utf-8')

def patch_host(src,out):
    b=bytearray(Path(src).read_bytes())
    if hashlib.sha256(b).hexdigest()!=HOST_SHA: raise SystemExit('HOST_SOURCE_SHA_FAIL')
    u16=lambda o:struct.unpack_from('<H',b,o)[0]; u32=lambda o:struct.unpack_from('<I',b,o)[0]
    def p16(o,v):struct.pack_into('<H',b,o,v)
    def p32(o,v):struct.pack_into('<I',b,o,v)
    A=lambda x,a:(x+a-1)//a*a
    pe=u32(0x3c);n=u16(pe+6);osz=u16(pe+20);opt=pe+24;s0=opt+osz;sa=u32(opt+32);fa=u32(opt+36);sh=u32(opt+60);sec=[]
    for i in range(n):
        o=s0+40*i;sec.append((u32(o+8),u32(o+12),u32(o+16),u32(o+20),u32(o+36),o))
    _,tva,trs,trp,_,_=max((s for s in sec if s[4]&0x20000000),key=lambda s:s[2]);sites=[]
    for x in range(trp,trp+trs-6):
        if b[x:x+2]==b'\x81\xec':
            z=u32(x+2)
            if 0x1000<=z<0x100000:sites.append((x,tva+x-trp,z))
    if len(sites)!=12:raise SystemExit('HOST_SITE_COUNT_'+str(len(sites)))
    chk=bytearray(b'\x51\x8d\x4c\x24\x04\x29\xc1\x19\xc0\xf7\xd0\x21\xc1\x89\xe0\x25\x00\xf0\xff\xff');loop=len(chk);chk+=b'\x39\xc1\x72\x00';jb=len(chk)-1;chk+=b'\x89\xc8\x59\x94\x8b\x00\x89\x04\x24\xc3';probe=len(chk);chk+=b'\x2d\x00\x10\x00\x00\x85\x00\xeb\x00';jm=len(chk)-1;chk[jb]=(probe-jb-1)&255;chk[jm]=(loop-jm-1)&255
    nh=s0+40*n;rp=A(max(s[3]+s[2] for s in sec),fa);va=A(max(s[1]+max(s[0],s[2]) for s in sec),sa);pay=bytearray(b'\x90'*120)+chk;rs=A(len(pay),fa)
    if nh+40>sh:raise SystemExit('HOST_NO_SECTION_HEADER_ROOM')
    b.extend(b'\0'*max(0,rp+rs-len(b)));b[rp:rp+len(pay)]=pay;cr=va+120
    for i,(x,r,z) in enumerate(sites):
        tr=va+10*i;to=rp+10*i;b[to]=0xb8;struct.pack_into('<I',b,to+1,z);b[to+5]=0xe9;struct.pack_into('<i',b,to+6,cr-(tr+10));b[x]=0xe8;struct.pack_into('<i',b,x+1,tr-(r+5));b[x+5]=0x90
    b[nh:nh+8]=b'.stkfix\0';p32(nh+8,len(pay));p32(nh+12,va);p32(nh+16,rs);p32(nh+20,rp);p32(nh+24,0);p32(nh+28,0);p16(nh+32,0);p16(nh+34,0);p32(nh+36,0x60000020);p16(pe+6,n+1);p32(opt+56,A(va+len(pay),sa));p32(opt+64,0)
    Path(out).write_bytes(b)
    if sha(out)!=HOSTFIX_SHA:raise SystemExit('HOSTFIX_SHA_FAIL_'+sha(out))
    return sites

def patch_harness(p):
    if sha(p)!=HARNESS_IN:raise SystemExit('HARNESS_SOURCE_SHA_FAIL_'+sha(p))
    s=Path(p).read_text().replace('\r\n','\n').replace('\r','\n')
    reps=[
      ('for(i=0;i<20000;i++){seq=a.proc(f.ids,f.samples,(int)f.n,0,state,result);','for(i=0;i<20000;i++){memset(state,0,sizeof(state));memset(result,0,sizeof(result));seq=a.proc(f.ids,f.samples,(int)f.n,0,state,result);'),
      ('for(i=0;i<t->loops;i++){uint32_t s=t->a->proc(t->f->ids,t->f->samples,(int)t->f->n,0,state,result);','for(i=0;i<t->loops;i++){uint32_t s;memset(state,0,sizeof(state));memset(result,0,sizeof(result));s=t->a->proc(t->f->ids,t->f->samples,(int)t->f->n,0,state,result);'),
      ('if(r!=1){fprintf(stderr,"realtime insufficient frames\\n");return 52;}if(!a.proc(f.ids,f.samples,(int)f.n,0,state,result))','if(r!=1){fprintf(stderr,"realtime insufficient frames\\n");return 52;}memset(state,0,sizeof(state));memset(result,0,sizeof(result));if(!a.proc(f.ids,f.samples,(int)f.n,0,state,result))'),
      ('if(!api_open(&a,argv[2],argv[3])){frame_free(&f);return 71;}s=a.proc(f.ids,f.samples,(int)f.n,0,state,result);','if(!api_open(&a,argv[2],argv[3])){frame_free(&f);return 71;}memset(state,0,sizeof(state));memset(result,0,sizeof(result));s=a.proc(f.ids,f.samples,(int)f.n,0,state,result);')]
    for a,b in reps:
        if a not in s:raise SystemExit('HARNESS_PATCH_PATTERN_MISSING')
        s=s.replace(a,b)
    Path(p).write_bytes(crlf_bytes(s))
    if sha(p)!=HARNESS_OUT:raise SystemExit('HARNESS_OUT_SHA_FAIL_'+sha(p))

def patch_runner(src,out):
    s=Path(src).read_text().replace('\r\n','\n').replace('\r','\n')
    old="function Run-Native([string]$Log,[string[]]$Args){\n    & $exe @Args *> $Log"
    new="function Run-Native {\n    param([string]$Log,[Parameter(ValueFromRemainingArguments=$true)][string[]]$NativeArgs)\n    & $exe @NativeArgs *> $Log"
    if old not in s:raise SystemExit('RUNNER_ARGS_NEEDLE')
    s=s.replace(old,new)
    calls={
      "Run-Native 'hostcompat_nonzero.log' @('baseline',$hostDll,$rtHost,$innerFrame)":"Run-Native 'hostcompat_nonzero.log' 'baseline' $hostDll $rtHost $innerFrame",
      "Run-Native 'c63_nonzero.log' @('baseline',$c63,$rtC63,$innerFrame)":"Run-Native 'c63_nonzero.log' 'baseline' $c63 $rtC63 $innerFrame",
      "Run-Native '01_sentinel.log' @('sentinel',$cand,$rtSent,$test)":"Run-Native '01_sentinel.log' 'sentinel' $cand $rtSent $test",
      "Run-Native '02_long.log' @('long',$cand,$rtLong,$innerFrame)":"Run-Native '02_long.log' 'long' $cand $rtLong $innerFrame",
      "Run-Native '03_threads.log' @('threads',$dllA,$dllB,$rtThr,$innerFrame)":"Run-Native '03_threads.log' 'threads' $dllA $dllB $rtThr $innerFrame",
      "Run-Native '04_full.log' @('full',$cand,$rtFI,$rtFO,$test)":"Run-Native '04_full.log' 'full' $cand $rtFI $rtFO $test",
      "Run-Native '05_determinism.log' @('determinism',$cand,$r1i,$r1o,$r2i,$r2o,$test)":"Run-Native '05_determinism.log' 'determinism' $cand $r1i $r1o $r2i $r2o $test",
      "Run-Native '06_realtime.log' @('realtime',$cand,$rtReal,$innerFrame)":"Run-Native '06_realtime.log' 'realtime' $cand $rtReal $innerFrame"}
    for a,b in calls.items():
        if a not in s:raise SystemExit('RUNNER_CALL_NEEDLE_'+a)
        s=s.replace(a,b)
    s=s.replace("$hostDll = (Resolve-Path 'payload\\HostCompat.dll').Path\n", "$hostDll = (Resolve-Path 'payload\\HostCompat.dll').Path\n$hostFixed = (Resolve-Path 'payload\\HostCompat-stackprobe-fixed.dll').Path\n")
    s=s.replace("Assert-Sha $hostDll $env:HOST_SHA\n", "Assert-Sha $hostDll $env:HOST_SHA\nAssert-Sha $hostFixed $env:HOST_FIXED_SHA\n")
    oldblock="""if(-not (Select-String -Path loader_inner.log -Pattern 'ALL_LOADER_CONTRACT_TESTS_PASS' -SimpleMatch -Quiet)){throw 'INNER_LOADER_MARKER_FAIL'}
if(-not (Select-String -Path loader_outer.log -Pattern 'ALL_LOADER_CONTRACT_TESTS_PASS' -SimpleMatch -Quiet)){throw 'OUTER_LOADER_MARKER_FAIL'}

# HostCompat and C63 real non-zero baselines
$rtHost=Copy-Runtime 'payload\\runtime\\inner-bed' 'rt_host_base'
$rtC63=Copy-Runtime 'payload\\runtime\\inner-bed' 'rt_c63_base'
Run-Native 'hostcompat_nonzero.log' 'baseline' $hostDll $rtHost $innerFrame
Run-Native 'c63_nonzero.log' 'baseline' $c63 $rtC63 $innerFrame
'NATIVE_LOADER_INNER_OUTER_HOSTCOMPAT_C63_PASS' | Set-Content native_loader_baseline_gate.txt
"""
    newblock="""if(-not (Select-String -Path loader_inner.log -Pattern 'ALL_LOADER_CONTRACT_TESTS_PASS' -SimpleMatch -Quiet)){throw 'INNER_LOADER_MARKER_FAIL'}
if(-not (Select-String -Path loader_outer.log -Pattern 'ALL_LOADER_CONTRACT_TESTS_PASS' -SimpleMatch -Quiet)){throw 'OUTER_LOADER_MARKER_FAIL'}
# Original HostCompat remains the loader/import compatibility reference; its nonzero path is stack-unsafe.
$rtHI=Copy-Runtime 'payload\\runtime\\inner-bed' 'rt_host_loader_inner'
$rtHO=Copy-Runtime 'payload\\runtime\\outer-medical-bed' 'rt_host_loader_outer'
foreach($rt in @($rtHI,$rtHO)){Copy-Item $hostDll \"$rt\\SigProcDll-64HF.dll\" -Force;Copy-Item $smoke \"$rt\\SigProcLoaderContractSmoke.exe\" -Force}
Push-Location $rtHI; .\\SigProcLoaderContractSmoke.exe *> \"$root\\hostcompat_loader_inner.log\"; $rc=$LASTEXITCODE; Pop-Location; Get-Content hostcompat_loader_inner.log; if($rc -ne 0){throw \"HOST_INNER_LOADER_FAIL $rc\"}
Push-Location $rtHO; .\\SigProcLoaderContractSmoke.exe *> \"$root\\hostcompat_loader_outer.log\"; $rc=$LASTEXITCODE; Pop-Location; Get-Content hostcompat_loader_outer.log; if($rc -ne 0){throw \"HOST_OUTER_LOADER_FAIL $rc\"}
if(-not (Select-String -Path hostcompat_loader_inner.log -Pattern 'ALL_LOADER_CONTRACT_TESTS_PASS' -SimpleMatch -Quiet)){throw 'HOST_INNER_LOADER_MARKER_FAIL'}
if(-not (Select-String -Path hostcompat_loader_outer.log -Pattern 'ALL_LOADER_CONTRACT_TESTS_PASS' -SimpleMatch -Quiet)){throw 'HOST_OUTER_LOADER_MARKER_FAIL'}

# Real non-zero: candidate first, C63 second, stack-probe-fixed HostCompat third.
$rtCand=Copy-Runtime 'payload\\runtime\\inner-bed' 'rt_candidate_base'
$rtC63=Copy-Runtime 'payload\\runtime\\inner-bed' 'rt_c63_base'
$rtHostFix=Copy-Runtime 'payload\\runtime\\inner-bed' 'rt_hostfix_base'
Run-Native 'candidate_nonzero.log' 'baseline' $cand $rtCand $innerFrame
Run-Native 'c63_nonzero.log' 'baseline' $c63 $rtC63 $innerFrame
Run-Native 'hostcompat_fixed_nonzero.log' 'baseline' $hostFixed $rtHostFix $innerFrame
'NATIVE_CANDIDATE_C63_HOSTFIX_NONZERO_PASS' | Set-Content native_loader_baseline_gate.txt
"""
    if oldblock not in s:raise SystemExit('RUNNER_BASELINE_BLOCK_NEEDLE')
    s=s.replace(oldblock,newblock)
    Path(out).write_bytes(crlf_bytes(s))
    if sha(out)!=RUNNER_OUT:raise SystemExit('RUNNER_OUT_SHA_FAIL_'+sha(out))

sites=patch_host('payload/HostCompat.dll','payload/HostCompat-stackprobe-fixed.dll')
patch_harness('payload/fullreg_c8b8.c')
patch_runner('.c8b8_resume_support/run_windows_gate_fixed_v2.ps1','payload/run_windows_gate.ps1')
Path('prepare_gate_v5.txt').write_text('PREPARE_GATE_V5_PASS\nHOSTFIX_SHA='+sha('payload/HostCompat-stackprobe-fixed.dll')+'\nHOST_PATCHED_SITES='+str(len(sites))+'\nHARNESS_SHA='+sha('payload/fullreg_c8b8.c')+'\nRUNNER_SHA='+sha('payload/run_windows_gate.ps1')+'\n')
print(Path('prepare_gate_v5.txt').read_text())
