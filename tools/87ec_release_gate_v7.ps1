$ErrorActionPreference = 'Stop'
$root = (Get-Location).Path

function Assert-Sha([string]$Path,[string]$Expected,[string]$Name){
    $h=(Get-FileHash $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if($h -ne $Expected){ throw "$Name SHA_FAIL actual=$h expected=$Expected path=$Path" }
    "$Name=$h  $Path" | Add-Content exact_asset_hashes.txt
    return $h
}
function Assert-Marker([string]$Path,[string]$Marker,[string]$Name){
    if(-not (Select-String -Path $Path -Pattern $Marker -SimpleMatch -Quiet)){ throw "$Name MARKER_FAIL [$Marker] path=$Path" }
}
function Copy-Runtime([string]$Source,[string]$Dest){
    if(Test-Path $Dest){Remove-Item $Dest -Recurse -Force}
    New-Item -ItemType Directory -Force $Dest | Out-Null
    Copy-Item "$Source\*" $Dest -Recurse -Force
    return (Resolve-Path $Dest).Path
}
function Run-Native([string]$Log,[string[]]$RunArgs){
    & $script:FullregExe @RunArgs *> $Log
    $rc=$LASTEXITCODE
    Get-Content $Log
    if($rc -ne 0){ throw "NATIVE_FAIL rc=$rc log=$Log args=$($RunArgs -join ' | ')" }
}

# 1) Recover immutable decrypted full-regression checkpoint.
$xz=(Resolve-Path 'checkpoint\c8b8_fullreg_payload_v2.tar.xz').Path
$checkpointSha=Assert-Sha $xz $env:CHECKPOINT_XZ_SHA 'CHECKPOINT_XZ_SHA'
New-Item -ItemType Directory -Force xzstage,expanded,payload | Out-Null
7z x -y $xz "-o$root\xzstage" | Out-Null
$tar=Get-ChildItem xzstage -Filter '*.tar' | Select-Object -First 1
if(!$tar){throw 'CHECKPOINT_TAR_MISSING'}
7z x -y $tar.FullName "-o$root\expanded" | Out-Null
$src=(Resolve-Path 'expanded\c8b8_fullreg_payload_v2').Path
Copy-Item "$src\*" payload -Recurse -Force

$parentSha=Assert-Sha 'payload\SigProcDll-64HF.dll' $env:PARENT_SHA 'CHECKPOINT_PARENT_C8B8_SHA'
$rawHostSha=Assert-Sha 'payload\HostCompat.dll' $env:RAW_HOST_SHA 'RAW_HOSTCOMPAT_SHA'
Assert-Sha 'payload\C63.dll' $env:C63_SHA 'C63_SHA' | Out-Null
Assert-Sha 'payload\SigProcLoaderContractSmoke.exe' $env:SMOKE_SHA 'LOADER_SMOKE_SHA' | Out-Null
Assert-Sha 'payload\fullreg_c8b8.c' $env:HARNESS_SHA 'FULLREG_C_HARNESS_SHA' | Out-Null
Copy-Item 'payload\HostCompat.dll' 'raw_HostCompat_original.dll' -Force

# 2) Bind exact 87ec production candidate that already passed the core-native Windows gate.
$cands=@(Get-ChildItem core87 -Recurse -Filter 'SigProcDll-64HF.dll' | Where-Object { (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -eq $env:CAND_SHA })
if($cands.Count -ne 1){throw "EXACT_87EC_CANDIDATE_COUNT_FAIL count=$($cands.Count)"}
Copy-Item $cands[0].FullName 'payload\SigProcDll-64HF.dll' -Force
$candSha=Assert-Sha 'payload\SigProcDll-64HF.dll' $env:CAND_SHA 'PRODUCTION_87EC_SHA'
$coreLock=Get-ChildItem core87 -Recurse -Filter 'C8B8_THREADFIX_V8_CORE_PASS.lock' | Select-Object -First 1
if(!$coreLock){throw 'CORE_NATIVE_PASS_LOCK_MISSING'}
$coreText=Get-Content $coreLock.FullName -Raw
foreach($m in @('THREADFIX_V8_CORE_NATIVE_PASS',"SHA256=$env:CAND_SHA",'TWO_THREAD=2x2000','LONG_STABILITY=20000','REALTIME_1HZ=60','RUN_ID=31298060637')){if(-not $coreText.Contains($m)){throw "CORE_LOCK_MARKER_FAIL $m"}}
Copy-Item $coreLock.FullName '87ec_core_native_pass.lock' -Force
foreach($p in @('threadstress_v8.log','stability_v8.log','realtime_v8.log','loader_inner-bed.log','loader_outer-medical-bed.log','cp08_corepass.txt')){
    $f=Get-ChildItem core87 -Recurse -Filter $p | Select-Object -First 1
    if(!$f){throw "CORE_EVIDENCE_MISSING $p"}
    Copy-Item $f.FullName ".\core_$p" -Force
}
Assert-Marker 'core_threadstress_v8.log' 'TWO_THREAD_STRESS_PASS threads=2 loops_each=2000' 'CORE_THREAD'
Assert-Marker 'core_stability_v8.log' 'LONG_STABILITY_PASS loops=20000' 'CORE_STABILITY'
Assert-Marker 'core_realtime_v8.log' 'REALTIME_1HZ_PASS frames=60' 'CORE_REALTIME'
Assert-Marker 'core_loader_inner-bed.log' 'ALL_LOADER_CONTRACT_TESTS_PASS' 'CORE_LOADER_INNER'
Assert-Marker 'core_loader_outer-medical-bed.log' 'ALL_LOADER_CONTRACT_TESTS_PASS' 'CORE_LOADER_OUTER'
Assert-Marker 'core_cp08_corepass.txt' "POST_TEST_SHA=$env:CAND_SHA" 'CORE_POST_SHA'

# 3) Bind exact stack-probe-safe HostCompat baseline fixture. This is NOT the production DLL.
$fixture=Get-ChildItem ba15fixture -Recurse -Filter 'SigProcDll-HostCompat-StackProbeSafe-ba15.dll' | Select-Object -First 1
if(!$fixture){throw 'BA15_FIXTURE_MISSING'}
$fixtureSha=Assert-Sha $fixture.FullName $env:BA15_SHA 'BA15_BASELINE_FIXTURE_SHA'
if($fixture.Length -ne 440320){throw "BA15_SIZE_FAIL $($fixture.Length)"}
Copy-Item $fixture.FullName 'payload\HostCompat.dll' -Force
Assert-Sha 'payload\HostCompat.dll' $env:BA15_SHA 'BOUND_BASELINE_FIXTURE_SHA' | Out-Null
$fixtureLock=Get-ChildItem ba15fixture -Recurse -Filter 'BA15_EXACT_RECOVERY_PASS.lock' | Select-Object -First 1
if(!$fixtureLock){throw 'BA15_RECOVERY_LOCK_MISSING'}
Assert-Marker $fixtureLock.FullName "SHA256=$env:BA15_SHA" 'BA15_RECOVERY_LOCK'
$fixtureStatic=Get-ChildItem ba15fixture -Recurse -Filter 'ba15_static_gate.txt' | Select-Object -First 1
if(!$fixtureStatic){throw 'BA15_STATIC_GATE_MISSING'}
Assert-Marker $fixtureStatic.FullName 'BA15_STATIC_FIXTURE_GATE_PASS' 'BA15_STATIC_GATE'

# 4) Lock all original GHF files byte-for-byte.
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
foreach($p in $ghf.Keys){Assert-Sha $p $ghf[$p] "GHF_$p" | Out-Null}
$files=@(Get-ChildItem payload\testdata -Recurse -Filter '*.ghf')
$count=$files.Count;$bytes=($files|Measure-Object Length -Sum).Sum
if($count -ne 13 -or $bytes -ne 82484656){throw "GHF_COVERAGE_FAIL count=$count bytes=$bytes"}
'ALL_13_ORIGINAL_GHF_SHA_PASS' | Set-Content ghf_sha_gate.txt

# 5) Independent PE / exports / imports / direct-large-stack audit.
$cand=(Resolve-Path 'payload\SigProcDll-64HF.dll').Path
$rawHost=(Resolve-Path 'raw_HostCompat_original.dll').Path
$baseFixture=(Resolve-Path 'payload\HostCompat.dll').Path
$c63=(Resolve-Path 'payload\C63.dll').Path
$smoke=(Resolve-Path 'payload\SigProcLoaderContractSmoke.exe').Path
$srcC=(Resolve-Path 'payload\fullreg_c8b8.c').Path
$testRoot=(Resolve-Path 'payload\testdata').Path
$innerFrame=(Resolve-Path 'payload\testdata\inner-bed\02_supine.ghf').Path

dumpbin /headers $cand | Out-File candidate_headers.txt
dumpbin /exports $cand | Out-File candidate_exports.txt
dumpbin /dependents $cand | Out-File candidate_dependents.txt
dumpbin /headers $baseFixture | Out-File ba15_headers_final.txt
dumpbin /exports $baseFixture | Out-File ba15_exports_final.txt
dumpbin /dependents $baseFixture | Out-File ba15_dependents_final.txt
dumpbin /exports $rawHost | Out-File raw_hostcompat_exports.txt
dumpbin /dependents $rawHost | Out-File raw_hostcompat_dependents.txt
Assert-Marker candidate_headers.txt '14C machine (x86)' 'CANDIDATE_X86'
Assert-Marker ba15_headers_final.txt '14C machine (x86)' 'BA15_X86'
foreach($e in @('_SigProc@24','_SigProc_Fini@0','_SigProc_Init@8','_SigProc_Stat@0')){
    Assert-Marker candidate_exports.txt $e "CANDIDATE_EXPORT_$e"
    Assert-Marker ba15_exports_final.txt $e "BA15_EXPORT_$e"
    Assert-Marker raw_hostcompat_exports.txt $e "RAW_HOST_EXPORT_$e"
}
@'
from pathlib import Path
import re,struct,sys

def deps(path):
    s=Path(path).read_text(errors='ignore');out=set();capture=False
    for line in s.splitlines():
        t=line.strip()
        if t.startswith('Image has the following dependencies'):capture=True;continue
        if capture and re.fullmatch(r'[A-Za-z0-9_.-]+\.dll',t,re.I):out.add(t.lower())
    return out

def direct_large(path):
    b=Path(path).read_bytes();u16=lambda o:struct.unpack_from('<H',b,o)[0];u32=lambda o:struct.unpack_from('<I',b,o)[0]
    pe=u32(0x3c);n=u16(pe+6);osz=u16(pe+20);s0=pe+24+osz;bad=[]
    for i in range(n):
        o=s0+40*i;name=b[o:o+8].split(b'\0',1)[0].decode('ascii','ignore');rs=u32(o+16);rp=u32(o+20);ch=u32(o+36)
        if ch & 0x20000000:
            for x in range(rp,max(rp,rp+rs-6)):
                if b[x:x+2]==b'\x81\xec':
                    imm=u32(x+2)
                    if 0x1000<=imm<0x100000:bad.append((name,x,imm))
    return bad

c=deps('candidate_dependents.txt');raw=deps('raw_hostcompat_dependents.txt');safe=deps('ba15_dependents_final.txt')
if raw!=safe:sys.exit('BA15_IMPORT_SET_NOT_RAW_HOSTCOMPAT_EQUAL raw='+repr(sorted(raw))+' safe='+repr(sorted(safe)))
if 'ucrtbase.dll' in c:sys.exit('DIRECT_UCRTBASE_IMPORT_FAIL')
extra=sorted(c-raw)
if extra:sys.exit('PRODUCTION_IMPORT_NOT_HOSTCOMPAT_SUBSET '+','.join(extra))
for p in ['payload/SigProcDll-64HF.dll','payload/HostCompat.dll']:
    bad=direct_large(p)
    if bad:sys.exit('LARGE_DIRECT_ESP_RESERVATION '+p+' '+repr(bad))
for p,marker in [('payload/SigProcDll-64HF.dll',b'.stkfix'),('payload/SigProcDll-64HF.dll',b'.thrfix'),('payload/HostCompat.dll',b'.stkfix')]:
    if marker not in Path(p).read_bytes():sys.exit('SECTION_MARKER_MISSING '+p+' '+marker.decode())
Path('static_pe_gate.txt').write_text('PE32_X86_PASS\nEXPORTS_PASS\nPRODUCTION_IMPORT_SUBSET_PASS\nBA15_RAW_HOSTCOMPAT_IMPORT_EQUAL_PASS\nSTKFIX_PRESENT\nTHRFIX_PRESENT\nLARGE_DIRECT_ESP_RESERVATIONS=0\n')
'@ | Set-Content -Encoding ascii $env:RUNNER_TEMP\v7_static.py
python $env:RUNNER_TEMP\v7_static.py *> static_gate_python.log
if($LASTEXITCODE -ne 0){Get-Content static_gate_python.log;throw 'STATIC_GATE_FAIL'}
Get-Content static_pe_gate.txt

# 6) Compile the unchanged original C full-regression harness under MSVC x86.
cl /nologo /O2 /W4 /D_CRT_SECURE_NO_WARNINGS /Fe:fullreg_c8b8.exe $srcC *> fullreg_compile.txt
if($LASTEXITCODE -ne 0){Get-Content fullreg_compile.txt;throw 'FULLREG_COMPILE_FAIL'}
if(!(Test-Path fullreg_c8b8.exe)){throw 'FULLREG_EXE_MISSING'}
$script:FullregExe=(Resolve-Path 'fullreg_c8b8.exe').Path
'FULLREG_X86_COMPILE_PASS' | Add-Content fullreg_compile.txt

# 7) Canonical production loader contract in both runtime layouts.
$rtLI=Copy-Runtime 'payload\runtime\inner-bed' 'rt_loader_inner'
$rtLO=Copy-Runtime 'payload\runtime\outer-medical-bed' 'rt_loader_outer'
foreach($rt in @($rtLI,$rtLO)){Copy-Item $cand "$rt\SigProcDll-64HF.dll" -Force;Copy-Item $smoke "$rt\SigProcLoaderContractSmoke.exe" -Force}
Push-Location $rtLI; .\SigProcLoaderContractSmoke.exe *> "$root\loader_inner.log"; $rc1=$LASTEXITCODE; Pop-Location
Push-Location $rtLO; .\SigProcLoaderContractSmoke.exe *> "$root\loader_outer.log"; $rc2=$LASTEXITCODE; Pop-Location
Get-Content loader_inner.log;Get-Content loader_outer.log
if($rc1 -ne 0 -or $rc2 -ne 0){throw "LOADER_CONTRACT_EXIT_FAIL inner=$rc1 outer=$rc2"}
Assert-Marker loader_inner.log 'ALL_LOADER_CONTRACT_TESTS_PASS' 'LOADER_INNER'
Assert-Marker loader_outer.log 'ALL_LOADER_CONTRACT_TESTS_PASS' 'LOADER_OUTER'

# 8) Real non-zero baseline survivability. BA15 is only the stack-probe-safe HostCompat fixture; C63 stays original.
$rtBase=Copy-Runtime 'payload\runtime\inner-bed' 'rt_hostcompat_safe_baseline'
$rtC63=Copy-Runtime 'payload\runtime\inner-bed' 'rt_c63_baseline'
Run-Native 'hostcompat_safe_nonzero.log' @('baseline',$baseFixture,$rtBase,$innerFrame)
Run-Native 'c63_nonzero.log' @('baseline',$c63,$rtC63,$innerFrame)
Assert-Marker hostcompat_safe_nonzero.log 'BASELINE_NATIVE_NONZERO_PASS' 'BA15_BASELINE_NONZERO'
Assert-Marker c63_nonzero.log 'BASELINE_NATIVE_NONZERO_PASS' 'C63_BASELINE_NONZERO'
@(
  'BASELINE_GATE_PASS',
  "RAW_HOSTCOMPAT_SHA=$rawHostSha",
  'RAW_HOSTCOMPAT_KNOWN_REAL_NONZERO_CRASH_RUN=31322471614',
  'RAW_HOSTCOMPAT_KNOWN_REAL_NONZERO_CRASH_CODE=0xC0000005',
  "STACKPROBE_SAFE_BASELINE_FIXTURE_SHA=$fixtureSha",
  'STACKPROBE_SAFE_BASELINE_FIXTURE_SCOPE=SURVIVABILITY_ONLY',
  'BA15_RAW_HOSTCOMPAT_IMPORT_EQUAL=PASS',
  'C63_ORIGINAL_BASELINE=PASS'
) | Set-Content baseline_fixture_gate.txt

# 9) Production exact 87ec: desired semantic sequence, crash path, concurrency, full 13 GHF, determinism, wall-clock 1Hz.
$rtSent=Copy-Runtime 'payload\runtime\outer-medical-bed' 'rt_sentinel'
Run-Native '01_sentinel.log' @('sentinel',$cand,$rtSent,$testRoot)

$rtLong=Copy-Runtime 'payload\runtime\inner-bed' 'rt_long'
Run-Native '02_long.log' @('long',$cand,$rtLong,$innerFrame)

Copy-Item $cand 'payload\SigProcDll-threadA.dll' -Force
Copy-Item $cand 'payload\SigProcDll-threadB.dll' -Force
$dllA=(Resolve-Path 'payload\SigProcDll-threadA.dll').Path
$dllB=(Resolve-Path 'payload\SigProcDll-threadB.dll').Path
$rtThr=Copy-Runtime 'payload\runtime\inner-bed' 'rt_threads'
Run-Native '03_threads.log' @('threads',$dllA,$dllB,$rtThr,$innerFrame)

$rtFI=Copy-Runtime 'payload\runtime\inner-bed' 'rt_full_inner'
$rtFO=Copy-Runtime 'payload\runtime\outer-medical-bed' 'rt_full_outer'
Run-Native '04_full.log' @('full',$cand,$rtFI,$rtFO,$testRoot)

$r1i=Copy-Runtime 'payload\runtime\inner-bed' 'rt_det1_inner'
$r1o=Copy-Runtime 'payload\runtime\outer-medical-bed' 'rt_det1_outer'
$r2i=Copy-Runtime 'payload\runtime\inner-bed' 'rt_det2_inner'
$r2o=Copy-Runtime 'payload\runtime\outer-medical-bed' 'rt_det2_outer'
Run-Native '05_determinism.log' @('determinism',$cand,$r1i,$r1o,$r2i,$r2o,$testRoot)

$rtReal=Copy-Runtime 'payload\runtime\inner-bed' 'rt_realtime'
Run-Native '06_realtime.log' @('realtime',$cand,$rtReal,$innerFrame)

$required=@(
 @{f='01_sentinel.log';m='SEQ_TARGETS_VITAL_SUPPRESSION_RECOVERY_PASS'},
 @{f='02_long.log';m='LONG_STABILITY_PASS loops=20000'},
 @{f='03_threads.log';m='TWO_THREAD_STRESS_PASS threads=2 loops_each=2000'},
 @{f='04_full.log';m='FULL_GHF_NATIVE_PASS frames=10808 samples=6853006'},
 @{f='04_full.log';m='PERFORMANCE_PASS'},
 @{f='05_determinism.log';m='DETERMINISTIC_REPLAY_PASS'},
 @{f='06_realtime.log';m='REALTIME_1HZ_PASS frames=60'}
)
foreach($x in $required){Assert-Marker $x.f $x.m 'PRODUCTION_FULLREG'}
$perf=Select-String -Path '04_full.log' -Pattern 'PERFORMANCE_PASS avg_ms=([0-9.]+)' | Select-Object -Last 1
if(!$perf){throw 'PERFORMANCE_LINE_MISSING'}
$avg=[double]$perf.Matches[0].Groups[1].Value
if($avg -gt 100.0){throw "PERFORMANCE_STRICT_100MS_FAIL avg_ms=$avg"}
$postSha=Assert-Sha $cand $env:CAND_SHA 'POST_COMPLETE_FULLREG_PRODUCTION_SHA'
'COMPLETE_NATIVE_WINDOWS_REGRESSION_PASS' | Set-Content complete_regression_gate.txt
"POST_TEST_SHA256=$postSha" | Set-Content post_test_sha.txt

# 10) SHA-bound authoritative release lock. Be explicit about the baseline fixture substitution.
@(
 '87EC_EXACT_NATIVE_AND_COMPLETE_FULLREG_PASS',
 "SHA256=$postSha",
 "PARENT_SHA=$parentSha",
 'CORE_NATIVE_RUN=31298060637',
 "COMPLETE_FULLREG_RUN=$env:GITHUB_RUN_ID",
 'PRODUCTION_DLL=SigProcDll-64HF.dll',
 'PE32_X86=PASS',
 'EXPORTS=PASS',
 'IMPORT_SUBSET=PASS',
 'STACK_PROBE=PASS',
 'THREAD_SERIALIZATION=PASS',
 'LOADER_INNER_OUTER=PASS',
 'REAL_NONZERO_GHF=PASS',
 'GHF_COUNT=13',
 'GHF_BYTES=82484656',
 'FULL_GHF_FRAMES=10808',
 'FULL_GHF_SAMPLES=6853006',
 'SEQ_TARGETS=PASS',
 'DETERMINISTIC_REPLAY=PASS',
 'LONG_STABILITY_20000=PASS',
 'SAME_PROCESS_TWO_THREAD_2X2000=PASS',
 'REALTIME_1HZ_60=PASS',
 "PERFORMANCE_AVG_MS=$avg",
 'PERFORMANCE_STRICT_LE_100MS=PASS',
 "RAW_HOSTCOMPAT_SHA=$rawHostSha",
 'RAW_HOSTCOMPAT_REAL_NONZERO_STATUS=KNOWN_CRASH_0xC0000005_RUN_31322471614',
 "BASELINE_FIXTURE_SHA=$fixtureSha",
 'BASELINE_FIXTURE_ROLE=HOSTCOMPAT_STACKPROBE_SAFE_SURVIVABILITY_ONLY',
 'BASELINE_FIXTURE_RAW_IMPORT_EQUAL=PASS',
 'BASELINE_FIXTURE_800_REAL_FRAME_WINDOWS_HISTORY=RUN_31304410871',
 'C63_ORIGINAL_NONZERO_BASELINE=PASS'
) | Set-Content 87EC_EXACT_NATIVE_AND_COMPLETE_FULLREG_PASS.lock

@(
 'GuanHu SigProc authoritative final release',
 'Filename=SigProcDll-64HF.dll',
 "SHA256=$postSha",
 'Architecture=PE32 x86',
 'Exports=_SigProc@24,_SigProc_Fini@0,_SigProc_Init@8,_SigProc_Stat@0',
 'CoreNativeRun=31298060637',
 "CompleteRegressionRun=$env:GITHUB_RUN_ID",
 'OriginalGHFCount=13',
 'OriginalGHFBytes=82484656',
 'FullFrames=10808',
 'FullSamples=6853006',
 "PerformanceAvgMs=$avg",
 "BaselineFixtureSHA=$fixtureSha",
 'BaselineFixtureScope=HostCompat stack-probe-safe survivability only; not production DLL',
 "RawHostCompatSHA=$rawHostSha",
 'RawHostCompatKnownRealNonzeroFailure=0xC0000005 in run 31322471614'
) | Set-Content FINAL_RELEASE_MANIFEST.txt

# 11) Final package and mandatory extract/re-hash audit.
New-Item -ItemType Directory -Force release | Out-Null
Copy-Item $cand 'release\SigProcDll-64HF.dll' -Force
Copy-Item '87EC_EXACT_NATIVE_AND_COMPLETE_FULLREG_PASS.lock','FINAL_RELEASE_MANIFEST.txt' release\ -Force
"$postSha  SigProcDll-64HF.dll" | Set-Content 'release\SigProcDll-64HF.dll.sha256'
Compress-Archive -Path 'release\*' -DestinationPath 'GuanHu_SigProc_Final_Release_20260809.zip' -Force
$zip=Get-Item 'GuanHu_SigProc_Final_Release_20260809.zip'
if($zip.Length -le 0){throw 'FINAL_ZIP_EMPTY'}
if(Test-Path zip_audit){Remove-Item zip_audit -Recurse -Force}
Expand-Archive $zip.FullName zip_audit -Force
$zdll=Get-Item 'zip_audit\SigProcDll-64HF.dll'
if($zdll.Length -le 0){throw 'ZIP_DLL_EMPTY'}
$zsha=(Get-FileHash $zdll.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
if($zsha -ne $env:CAND_SHA){throw "ZIP_EXTRACTED_DLL_SHA_FAIL $zsha"}
$zipsha=(Get-FileHash $zip.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
@('FINAL_ZIP_AUDIT_PASS',"ZIP_SHA256=$zipsha","EXTRACTED_DLL_SHA256=$zsha","EXTRACTED_DLL_BYTES=$($zdll.Length)") | Set-Content FINAL_ZIP_AUDIT_PASS.txt

# 12) Durable PASS lock in Git history.
New-Item -ItemType Directory -Force evidence_summary | Out-Null
Copy-Item '87EC_EXACT_NATIVE_AND_COMPLETE_FULLREG_PASS.lock','FINAL_RELEASE_MANIFEST.txt','FINAL_ZIP_AUDIT_PASS.txt','baseline_fixture_gate.txt','static_pe_gate.txt','ghf_sha_gate.txt','post_test_sha.txt','complete_regression_gate.txt' evidence_summary\ -Force
git config user.name windows-dll-test-bot
git config user.email windows-dll-test-bot@users.noreply.github.com
git add evidence_summary
git commit -m 'Lock authoritative exact 87ec complete native full regression PASS'
if($LASTEXITCODE -ne 0){throw 'FINAL_PASS_COMMIT_FAIL'}
git push origin "HEAD:$env:HANDOFF_BRANCH"
if($LASTEXITCODE -ne 0){throw 'FINAL_PASS_PUSH_FAIL'}
'87EC_AUTHORITATIVE_FINAL_RELEASE_GATE_PASS' | Set-Content 87ec_final_release_gate_pass.txt
