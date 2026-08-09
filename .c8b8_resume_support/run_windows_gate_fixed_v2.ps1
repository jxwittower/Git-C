$ErrorActionPreference = 'Stop'
$root = (Get-Location).Path
$cand = (Resolve-Path 'payload\SigProcDll-64HF.dll').Path
$hostDll = (Resolve-Path 'payload\HostCompat.dll').Path
$c63 = (Resolve-Path 'payload\C63.dll').Path
$smoke = (Resolve-Path 'payload\SigProcLoaderContractSmoke.exe').Path
$src = (Resolve-Path 'payload\fullreg_c8b8.c').Path
$test = (Resolve-Path 'payload\testdata').Path
$innerFrame = (Resolve-Path 'payload\testdata\inner-bed\02_supine.ghf').Path

function Assert-Sha([string]$Path,[string]$Expected) {
    $h=(Get-FileHash $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if($h -ne $Expected){ throw "SHA_FAIL $Path $h expected=$Expected" }
    "$h  $Path" | Add-Content exact_asset_hashes.txt
}
Assert-Sha $cand $env:CAND_SHA
Assert-Sha $hostDll $env:HOST_SHA
Assert-Sha $c63 $env:C63_SHA
Assert-Sha $smoke $env:SMOKE_SHA
Assert-Sha $src $env:HARNESS_SHA

$ghf=@{
'payload\testdata\inner-bed\01_initial_empty.ghf'='bdee0b60e66601d036925c6753f763020f517ff22504dc1080d6fd7fef16c798';
'payload\testdata\inner-bed\02_supine.ghf'='f9601b4f91b61bf15f554639f244ecb3617204b1102affdae5b3d7f6bfad0a7f';
'payload\testdata\inner-bed\03_left.ghf'='011426b2fd07ba2741a0fe890cbacb3f16766f1f7310160f6177fbbd1e557fbe';
'payload\testdata\inner-bed\04_right.ghf'='b5729623ddc5fed1b9a993658db1b84a699fe4a7e9a4183ef1433b7f392b4dfe';
'payload\testdata\inner-bed\05_free.ghf'='c4c4665fd9aff891b66aed223b67bfdb5af0a437d18385057acc7f675ad6b9cc';
'payload\testdata\inner-bed\06_final_empty.ghf'='6ee2b15321b1164b6f2de4b031b393a7227355d9e6b6b39dddddef57434da7e7';
'payload\testdata\outer-medical-bed\01_initial_empty.ghf'='226efcb270599df569b628118db8afa4e678296750afa651c5da376da79d3737';
'payload\testdata\outer-medical-bed\02_supine.ghf'='69f64f78d5a2e0d22f75086096117eda2d276ef734b763002d5cace97d17c7c0';
'payload\testdata\outer-medical-bed\03_left.ghf'='55558b1c850a5438f2815863e2102f958b4c9b137350622e36d5434a8c5da77c';
'payload\testdata\outer-medical-bed\04_right.ghf'='d54ae503fd68a9463fc48cbfa33af05d3b985aad8eb286d46359bf286ccc3afb';
'payload\testdata\outer-medical-bed\05_leave.ghf'='f2f2caa0e5e35dcc41f9d37c2bc0e70c11cc5b39062ec8025edd18394884866c';
'payload\testdata\outer-medical-bed\06_return_free.ghf'='99f93d049a6a84bc24bb6617f02de19b95dc17062ade0593ec33cec336dce948';
'payload\testdata\outer-medical-bed\07_final_empty.ghf'='4f7f9ba9a49ec39093c5883a3234bf468f2fee57c9a6392206d606ed1b9462c8'
}
foreach($p in $ghf.Keys){Assert-Sha $p $ghf[$p]}
$files=Get-ChildItem payload\testdata -Recurse -Filter '*.ghf'
$count=$files.Count; $bytes=($files|Measure-Object Length -Sum).Sum
if($count -ne 13 -or $bytes -ne 82484656){throw "GHF_COVERAGE_FAIL count=$count bytes=$bytes"}
"ASSET_BIND_PASS`nGHF_COUNT=$count`nGHF_BYTES=$bytes`nCAND_SHA=$env:CAND_SHA" | Set-Content exact_asset_binding.txt
'ALL_13_ORIGINAL_GHF_SHA_PASS' | Set-Content ghf_sha_gate.txt

# Static PE / ABI / stack gate
dumpbin /headers $cand | Out-File candidate_headers.txt
dumpbin /exports $cand | Out-File candidate_exports.txt
dumpbin /dependents $cand | Out-File candidate_dependents.txt
dumpbin /dependents $hostDll | Out-File hostcompat_dependents.txt
if(-not (Select-String -Path candidate_headers.txt -Pattern '14C machine (x86)' -SimpleMatch -Quiet)){throw 'PE32_X86_FAIL'}
if(-not (Select-String -Path candidate_headers.txt -Pattern '.stkfix' -SimpleMatch -Quiet)){throw 'STKFIX_SECTION_FAIL'}
foreach($e in @('_SigProc@24','_SigProc_Fini@0','_SigProc_Init@8','_SigProc_Stat@0')){if(-not (Select-String -Path candidate_exports.txt -Pattern $e -SimpleMatch -Quiet)){throw "EXPORT_FAIL $e"}}
@'
from pathlib import Path
import re,struct,sys
def deps(path):
    s=Path(path).read_text(errors='ignore'); out=set(); capture=False
    for line in s.splitlines():
        t=line.strip()
        if t.startswith('Image has the following dependencies'): capture=True; continue
        if capture and re.fullmatch(r'[A-Za-z0-9_.-]+\.dll',t,re.I): out.add(t.lower())
    return out
c=deps('candidate_dependents.txt'); h=deps('hostcompat_dependents.txt')
if 'ucrtbase.dll' in c: sys.exit('DIRECT_UCRTBASE_FAIL')
extra=sorted(c-h)
if extra: sys.exit('IMPORT_SUBSET_FAIL '+','.join(extra))
b=Path('payload/SigProcDll-64HF.dll').read_bytes()
u16=lambda o:struct.unpack_from('<H',b,o)[0]; u32=lambda o:struct.unpack_from('<I',b,o)[0]
pe=u32(0x3c); n=u16(pe+6); osz=u16(pe+20); s0=pe+24+osz; bad=[]
for i in range(n):
    o=s0+40*i; name=b[o:o+8].split(b'\0',1)[0].decode('ascii','ignore'); rs=u32(o+16); rp=u32(o+20); ch=u32(o+36)
    if ch & 0x20000000:
        for x in range(rp,max(rp,rp+rs-6)):
            if b[x:x+2]==b'\x81\xec':
                imm=u32(x+2)
                if 0x1000<=imm<0x100000: bad.append((name,x,imm))
if bad: sys.exit('LARGE_DIRECT_ESP_RESERVATION '+repr(bad))
Path('static_pe_gate.txt').write_text('PE32_X86_PASS\nEXPORTS_PASS\nIMPORT_SUBSET_PASS\nSTKFIX_PRESENT\nLARGE_DIRECT_ESP_RESERVATIONS=0\n')
'@ | Set-Content -Encoding ascii $env:RUNNER_TEMP\static_gate.py
python $env:RUNNER_TEMP\static_gate.py *> static_gate_python.log
if($LASTEXITCODE -ne 0){Get-Content static_gate_python.log;throw 'STATIC_GATE_FAIL'}

# Compile x86 harness
cl /nologo /O2 /W4 /D_CRT_SECURE_NO_WARNINGS /Fe:fullreg_c8b8.exe $src *> fullreg_compile.txt
if($LASTEXITCODE -ne 0){Get-Content fullreg_compile.txt;throw 'FULLREG_COMPILE_FAIL'}
if(!(Test-Path fullreg_c8b8.exe)){throw 'FULLREG_EXE_MISSING'}
'FULLREG_X86_COMPILE_PASS' | Add-Content fullreg_compile.txt
$exe=(Resolve-Path 'fullreg_c8b8.exe').Path

function Copy-Runtime([string]$src,[string]$dst){
    if(Test-Path $dst){Remove-Item $dst -Recurse -Force}
    New-Item -ItemType Directory -Force $dst | Out-Null
    Copy-Item "$src\*" $dst -Recurse -Force
    return (Resolve-Path $dst).Path
}
function Run-Native([string]$Log,[string[]]$Args){
    & $exe @Args *> $Log
    $rc=$LASTEXITCODE
    Get-Content $Log
    if($rc -ne 0){throw "NATIVE_FAIL rc=$rc log=$Log"}
}

# Canonical loader contract in both runtime layouts
$rtLI=Copy-Runtime 'payload\runtime\inner-bed' 'rt_loader_inner'
$rtLO=Copy-Runtime 'payload\runtime\outer-medical-bed' 'rt_loader_outer'
foreach($rt in @($rtLI,$rtLO)){Copy-Item $cand "$rt\SigProcDll-64HF.dll" -Force;Copy-Item $smoke "$rt\SigProcLoaderContractSmoke.exe" -Force}
Push-Location $rtLI; .\SigProcLoaderContractSmoke.exe *> "$root\loader_inner.log"; $rc=$LASTEXITCODE; Pop-Location; Get-Content loader_inner.log; if($rc -ne 0){throw "INNER_LOADER_FAIL $rc"}
Push-Location $rtLO; .\SigProcLoaderContractSmoke.exe *> "$root\loader_outer.log"; $rc=$LASTEXITCODE; Pop-Location; Get-Content loader_outer.log; if($rc -ne 0){throw "OUTER_LOADER_FAIL $rc"}
if(-not (Select-String -Path loader_inner.log -Pattern 'ALL_LOADER_CONTRACT_TESTS_PASS' -SimpleMatch -Quiet)){throw 'INNER_LOADER_MARKER_FAIL'}
if(-not (Select-String -Path loader_outer.log -Pattern 'ALL_LOADER_CONTRACT_TESTS_PASS' -SimpleMatch -Quiet)){throw 'OUTER_LOADER_MARKER_FAIL'}

# HostCompat and C63 real non-zero baselines
$rtHost=Copy-Runtime 'payload\runtime\inner-bed' 'rt_host_base'
$rtC63=Copy-Runtime 'payload\runtime\inner-bed' 'rt_c63_base'
Run-Native 'hostcompat_nonzero.log' @('baseline',$hostDll,$rtHost,$innerFrame)
Run-Native 'c63_nonzero.log' @('baseline',$c63,$rtC63,$innerFrame)
'NATIVE_LOADER_INNER_OUTER_HOSTCOMPAT_C63_PASS' | Set-Content native_loader_baseline_gate.txt

# Desired final algorithm behavior first: leave/vital suppression/recovery/final empty
$rtSent=Copy-Runtime 'payload\runtime\outer-medical-bed' 'rt_sentinel'
Run-Native '01_sentinel.log' @('sentinel',$cand,$rtSent,$test)
# Stack-probe crash path stress
$rtLong=Copy-Runtime 'payload\runtime\inner-bed' 'rt_long'
Run-Native '02_long.log' @('long',$cand,$rtLong,$innerFrame)
# Two independent copies in two threads in one process
Copy-Item $cand payload\SigProcDll-threadA.dll -Force
Copy-Item $cand payload\SigProcDll-threadB.dll -Force
$dllA=(Resolve-Path 'payload\SigProcDll-threadA.dll').Path; $dllB=(Resolve-Path 'payload\SigProcDll-threadB.dll').Path
$rtThr=Copy-Runtime 'payload\runtime\inner-bed' 'rt_threads'
Run-Native '03_threads.log' @('threads',$dllA,$dllB,$rtThr,$innerFrame)
# All 13 original GHF files, both bed runtimes
$rtFI=Copy-Runtime 'payload\runtime\inner-bed' 'rt_full_inner'; $rtFO=Copy-Runtime 'payload\runtime\outer-medical-bed' 'rt_full_outer'
Run-Native '04_full.log' @('full',$cand,$rtFI,$rtFO,$test)
# Full deterministic replay twice with fresh runtime copies
$r1i=Copy-Runtime 'payload\runtime\inner-bed' 'rt_det1_inner'; $r1o=Copy-Runtime 'payload\runtime\outer-medical-bed' 'rt_det1_outer'; $r2i=Copy-Runtime 'payload\runtime\inner-bed' 'rt_det2_inner'; $r2o=Copy-Runtime 'payload\runtime\outer-medical-bed' 'rt_det2_outer'
Run-Native '05_determinism.log' @('determinism',$cand,$r1i,$r1o,$r2i,$r2o,$test)
# Actual wall-clock 1Hz path
$rtReal=Copy-Runtime 'payload\runtime\inner-bed' 'rt_realtime'
Run-Native '06_realtime.log' @('realtime',$cand,$rtReal,$innerFrame)

$markers=@(
@{f='01_sentinel.log';m='SEQ_TARGETS_VITAL_SUPPRESSION_RECOVERY_PASS'},
@{f='02_long.log';m='LONG_STABILITY_PASS loops=20000'},
@{f='03_threads.log';m='TWO_THREAD_STRESS_PASS threads=2 loops_each=2000'},
@{f='04_full.log';m='FULL_GHF_NATIVE_PASS frames=10808 samples=6853006'},
@{f='04_full.log';m='PERFORMANCE_PASS'},
@{f='05_determinism.log';m='DETERMINISTIC_REPLAY_PASS'},
@{f='06_realtime.log';m='REALTIME_1HZ_PASS frames=60'}
)
foreach($x in $markers){if(-not (Select-String -Path $x.f -Pattern $x.m -SimpleMatch -Quiet)){throw "MARKER_FAIL $($x.m)"}}
$post=(Get-FileHash $cand -Algorithm SHA256).Hash.ToLowerInvariant()
if($post -ne $env:CAND_SHA){throw "POST_SHA_FAIL $post"}
"POST_TEST_SHA256=$post" | Set-Content post_test_sha.txt
"C8B8_EXACT_NATIVE_COMPLETE_REGRESSION_PASS SHA256=$post" | Set-Content C8B8_EXACT_NATIVE_AND_FULLREG_PASS.lock
'COMPLETE_NATIVE_WINDOWS_REGRESSION_PASS' | Set-Content complete_regression_gate.txt

# Commit the exact pass lock to the handoff branch; path filter prevents re-trigger.
New-Item -ItemType Directory -Force evidence_summary | Out-Null
Copy-Item C8B8_EXACT_NATIVE_AND_FULLREG_PASS.lock,post_test_sha.txt,complete_regression_gate.txt evidence_summary\ -Force
git config user.name windows-dll-test-bot
git config user.email windows-dll-test-bot@users.noreply.github.com
git add evidence_summary
git commit -m "Lock c8b8 exact native Windows complete regression PASS"
if($LASTEXITCODE -ne 0){throw 'PASS_COMMIT_FAIL'}
git push origin "HEAD:$env:HANDOFF_BRANCH"
if($LASTEXITCODE -ne 0){throw 'PASS_PUSH_FAIL'}
'RUN_WINDOWS_GATE_PASS' | Set-Content run_windows_gate_pass.txt
