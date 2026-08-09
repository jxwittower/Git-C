$ErrorActionPreference = 'Stop'

function Assert-Sha([string]$Path,[string]$Expected,[string]$Name){
  $h=(Get-FileHash $Path -Algorithm SHA256).Hash.ToLowerInvariant()
  if($h -ne $Expected){throw "$Name SHA_FAIL actual=$h expected=$Expected"}
  return $h
}

# A. Recover immutable decrypted checkpoint.
$xz=(Resolve-Path 'checkpoint\c8b8_fullreg_payload_v2.tar.xz').Path
$xh=Assert-Sha $xz $env:CHECKPOINT_XZ_SHA 'CHECKPOINT_XZ'
New-Item -ItemType Directory -Force xzstage,expanded,payload | Out-Null
7z x -y $xz "-o$pwd\xzstage" | Out-Null
$tar=Get-ChildItem xzstage -Filter '*.tar' | Select-Object -First 1
if(!$tar){throw 'CHECKPOINT_TAR_MISSING'}
7z x -y $tar.FullName "-o$pwd\expanded" | Out-Null
$src=(Resolve-Path 'expanded\c8b8_fullreg_payload_v2').Path
Copy-Item "$src\*" payload -Recurse -Force
$parent=Assert-Sha 'payload\SigProcDll-64HF.dll' $env:PARENT_SHA 'CHECKPOINT_PARENT_DLL'
Assert-Sha 'payload\HostCompat.dll' $env:HOST_SHA 'HOSTCOMPAT' | Out-Null
Assert-Sha 'payload\C63.dll' $env:C63_SHA 'C63' | Out-Null
Assert-Sha 'payload\SigProcLoaderContractSmoke.exe' $env:SMOKE_SHA 'LOADER_SMOKE' | Out-Null
Assert-Sha 'payload\fullreg_c8b8.c' $env:HARNESS_SHA 'FULLREG_HARNESS' | Out-Null

# B. Bind the exact DLL that already passed the real same-process core-native gate.
$cands=@(Get-ChildItem core87 -Recurse -Filter 'SigProcDll-64HF.dll' | Where-Object { (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -eq $env:CAND_SHA })
if($cands.Count -ne 1){throw "EXACT_87EC_CANDIDATE_COUNT_FAIL count=$($cands.Count)"}
Copy-Item $cands[0].FullName 'payload\SigProcDll-64HF.dll' -Force
$bound=Assert-Sha 'payload\SigProcDll-64HF.dll' $env:CAND_SHA 'BOUND_87EC_DLL'
$lock=Get-ChildItem core87 -Recurse -Filter 'C8B8_THREADFIX_V8_CORE_PASS.lock' | Select-Object -First 1
if(!$lock){throw 'CORE_NATIVE_PASS_LOCK_MISSING'}
$lt=Get-Content $lock.FullName -Raw
foreach($m in @('THREADFIX_V8_CORE_NATIVE_PASS',"SHA256=$env:CAND_SHA",'TWO_THREAD=2x2000','LONG_STABILITY=20000','REALTIME_1HZ=60','RUN_ID=31298060637')){if(-not $lt.Contains($m)){throw "CORE_LOCK_MARKER_FAIL $m"}}
Copy-Item $lock.FullName '87ec_core_native_pass.lock' -Force
foreach($p in @('threadstress_v8.log','stability_v8.log','realtime_v8.log','loader_inner-bed.log','loader_outer-medical-bed.log','cp08_corepass.txt')){
  $f=Get-ChildItem core87 -Recurse -Filter $p | Select-Object -First 1
  if(!$f){throw "CORE_EVIDENCE_MISSING $p"}
  Copy-Item $f.FullName ".\core_$p" -Force
}
if(-not(Select-String -Path 'core_threadstress_v8.log' -Pattern 'TWO_THREAD_STRESS_PASS threads=2 loops_each=2000' -SimpleMatch -Quiet)){throw 'CORE_THREAD_FAIL'}
if(-not(Select-String -Path 'core_stability_v8.log' -Pattern 'LONG_STABILITY_PASS loops=20000' -SimpleMatch -Quiet)){throw 'CORE_STABILITY_FAIL'}
if(-not(Select-String -Path 'core_realtime_v8.log' -Pattern 'REALTIME_1HZ_PASS frames=60' -SimpleMatch -Quiet)){throw 'CORE_REALTIME_FAIL'}
if(-not(Select-String -Path 'core_loader_inner-bed.log' -Pattern 'ALL_LOADER_CONTRACT_TESTS_PASS' -SimpleMatch -Quiet)){throw 'CORE_INNER_LOADER_FAIL'}
if(-not(Select-String -Path 'core_loader_outer-medical-bed.log' -Pattern 'ALL_LOADER_CONTRACT_TESTS_PASS' -SimpleMatch -Quiet)){throw 'CORE_OUTER_LOADER_FAIL'}
if(-not(Select-String -Path 'core_cp08_corepass.txt' -Pattern "POST_TEST_SHA=$env:CAND_SHA" -SimpleMatch -Quiet)){throw 'CORE_POST_SHA_FAIL'}

$raw=[IO.File]::ReadAllBytes((Resolve-Path 'payload\SigProcDll-64HF.dll'))
$ascii=[Text.Encoding]::ASCII.GetString($raw)
if(-not $ascii.Contains('.stkfix')){throw 'STKFIX_SECTION_MISSING'}
if(-not $ascii.Contains('.thrfix')){throw 'THRFIX_SECTION_MISSING'}
$ghf=@(Get-ChildItem payload\testdata -Recurse -Filter '*.ghf')
$ghfBytes=($ghf|Measure-Object Length -Sum).Sum
if($ghf.Count -ne 13 -or $ghfBytes -ne 82484656){throw "ORIGINAL_GHF_COVERAGE_FAIL count=$($ghf.Count) bytes=$ghfBytes"}

# C. Patch only PowerShell orchestration compatibility defects in the immutable runner.
#    C regression source, DLL, GHF and runtime assets remain byte-identical.
$runner='payload\run_windows_gate.ps1'
$runnerOriginal=Assert-Sha $runner $env:ORIGINAL_RUNNER_SHA 'ORIGINAL_WINDOWS_RUNNER'
$s=Get-Content $runner -Raw
$pairs=@(
  @('$host = (Resolve-Path ''payload\HostCompat.dll'').Path','$hostDll = (Resolve-Path ''payload\HostCompat.dll'').Path'),
  @('Assert-Sha $host $env:HOST_SHA','Assert-Sha $hostDll $env:HOST_SHA'),
  @('dumpbin /dependents $host | Out-File hostcompat_dependents.txt','dumpbin /dependents $hostDll | Out-File hostcompat_dependents.txt'),
  @("@('baseline',`$host,`$rtHost,`$innerFrame)","@('baseline',`$hostDll,`$rtHost,`$innerFrame)"),
  @("Select-String candidate_headers.txt -SimpleMatch '14C machine (x86)' -Quiet","Select-String -Path candidate_headers.txt -Pattern '14C machine (x86)' -SimpleMatch -Quiet"),
  @("Select-String candidate_headers.txt -SimpleMatch '.stkfix' -Quiet","Select-String -Path candidate_headers.txt -Pattern '.stkfix' -SimpleMatch -Quiet"),
  @('Select-String candidate_exports.txt -SimpleMatch $e -Quiet','Select-String -Path candidate_exports.txt -Pattern $e -SimpleMatch -Quiet'),
  @("Select-String loader_inner.log -SimpleMatch 'ALL_LOADER_CONTRACT_TESTS_PASS' -Quiet","Select-String -Path loader_inner.log -Pattern 'ALL_LOADER_CONTRACT_TESTS_PASS' -SimpleMatch -Quiet"),
  @("Select-String loader_outer.log -SimpleMatch 'ALL_LOADER_CONTRACT_TESTS_PASS' -Quiet","Select-String -Path loader_outer.log -Pattern 'ALL_LOADER_CONTRACT_TESTS_PASS' -SimpleMatch -Quiet"),
  @('Select-String $x.f -SimpleMatch $x.m -Quiet','Select-String -Path $x.f -Pattern $x.m -SimpleMatch -Quiet')
)
foreach($q in $pairs){
  if(-not $s.Contains($q[0])){throw "RUNNER_PATCH_TARGET_MISSING [$($q[0])]"}
  $s=$s.Replace($q[0],$q[1])
}
[IO.File]::WriteAllText((Resolve-Path $runner),$s,(New-Object Text.UTF8Encoding($false)))
$runnerPatched=(Get-FileHash $runner -Algorithm SHA256).Hash.ToLowerInvariant()
@(
  "CHECKPOINT_XZ_SHA=$xh","PARENT_SHA=$parent","BOUND_CANDIDATE_SHA=$bound","CORE_NATIVE_RUN=$env:CORE_RUN_ID",
  "GHF_COUNT=$($ghf.Count)","GHF_BYTES=$ghfBytes","ORIGINAL_RUNNER_SHA=$runnerOriginal","PATCHED_RUNNER_SHA=$runnerPatched",
  'PATCH_SCOPE=PowerShell Host variable rename + Select-String named parameters only','C_HARNESS_UNCHANGED=PASS','STKFIX=PASS','THRFIX=PASS'
) | Set-Content 87ec_exact_binding.txt

# D. Execute the complete native Windows regression supplied by the checkpoint.
& .\payload\run_windows_gate.ps1
if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}
if(!(Test-Path 'run_windows_gate_pass.txt')){throw 'RUN_WINDOWS_GATE_PASS_MISSING'}
if(-not(Select-String -Path 'complete_regression_gate.txt' -Pattern 'COMPLETE_NATIVE_WINDOWS_REGRESSION_PASS' -SimpleMatch -Quiet)){throw 'COMPLETE_NATIVE_WINDOWS_REGRESSION_MARKER_MISSING'}
$post=Assert-Sha 'payload\SigProcDll-64HF.dll' $env:CAND_SHA 'POST_COMPLETE_FULLREG_DLL'

# E. Independent strict final audit. Core PASS + complete 13-file PASS must bind to the same SHA.
$checks=@(
  @{f='01_sentinel.log';m='SEQ_TARGETS_VITAL_SUPPRESSION_RECOVERY_PASS'},
  @{f='02_long.log';m='LONG_STABILITY_PASS loops=20000'},
  @{f='03_threads.log';m='TWO_THREAD_STRESS_PASS threads=2 loops_each=2000'},
  @{f='04_full.log';m='FULL_GHF_NATIVE_PASS frames=10808 samples=6853006'},
  @{f='04_full.log';m='PERFORMANCE_PASS'},
  @{f='05_determinism.log';m='DETERMINISTIC_REPLAY_PASS'},
  @{f='06_realtime.log';m='REALTIME_1HZ_PASS frames=60'}
)
foreach($x in $checks){if(-not(Select-String -Path $x.f -Pattern $x.m -SimpleMatch -Quiet)){throw "FINAL_MARKER_FAIL $($x.m)"}}
$perf=Select-String -Path '04_full.log' -Pattern 'PERFORMANCE_PASS avg_ms=([0-9.]+)' | Select-Object -Last 1
if(!$perf){throw 'PERFORMANCE_LINE_MISSING'}
$avg=[double]$perf.Matches[0].Groups[1].Value
if($avg -gt 100.0){throw "PERFORMANCE_STRICT_100MS_FAIL avg_ms=$avg"}

@(
 '87EC_EXACT_NATIVE_AND_COMPLETE_FULLREG_PASS',"SHA256=$post",'PARENT_SHA=c8b8f49620b45707f80f47a9fadf14db376a115bc6052517e9243e0cb2dc20e9',
 'CORE_NATIVE_RUN=31298060637',"COMPLETE_FULLREG_RUN=$env:GITHUB_RUN_ID",'PE32_X86=PASS','EXPORTS=PASS','IMPORT_SUBSET=PASS',
 'STACK_PROBE=PASS','THREAD_SERIALIZATION=PASS','LOADER_INNER_OUTER=PASS','REAL_NONZERO_GHF=PASS','GHF_COUNT=13','GHF_BYTES=82484656',
 'FULL_GHF_FRAMES=10808','FULL_GHF_SAMPLES=6853006','SEQ_TARGETS=PASS','DETERMINISTIC_REPLAY=PASS','LONG_STABILITY_20000=PASS',
 'SAME_PROCESS_TWO_THREAD_2X2000=PASS','REALTIME_1HZ_60=PASS',"PERFORMANCE_AVG_MS=$avg",'PERFORMANCE_STRICT_LE_100MS=PASS'
) | Set-Content 87EC_EXACT_NATIVE_AND_COMPLETE_FULLREG_PASS.lock
@(
 'GuanHu SigProc authoritative final release','Filename=SigProcDll-64HF.dll',"SHA256=$post",'Architecture=PE32 x86',
 'Exports=_SigProc@24,_SigProc_Fini@0,_SigProc_Init@8,_SigProc_Stat@0','CoreNativeRun=31298060637',"CompleteRegressionRun=$env:GITHUB_RUN_ID",
 'OriginalGHFCount=13','OriginalGHFBytes=82484656','FullFrames=10808','FullSamples=6853006',"PerformanceAvgMs=$avg"
) | Set-Content FINAL_RELEASE_MANIFEST.txt

# F. Build and re-extract final ZIP; release artifact is created only after this exact SHA audit.
New-Item -ItemType Directory -Force release | Out-Null
Copy-Item 'payload\SigProcDll-64HF.dll' 'release\SigProcDll-64HF.dll' -Force
Copy-Item '87EC_EXACT_NATIVE_AND_COMPLETE_FULLREG_PASS.lock','FINAL_RELEASE_MANIFEST.txt' release\ -Force
"$post  SigProcDll-64HF.dll" | Set-Content 'release\SigProcDll-64HF.dll.sha256'
Compress-Archive -Path 'release\*' -DestinationPath 'GuanHu_SigProc_Final_Release_20260809.zip' -Force
if((Get-Item 'GuanHu_SigProc_Final_Release_20260809.zip').Length -le 0){throw 'FINAL_ZIP_EMPTY'}
if(Test-Path zip_audit){Remove-Item zip_audit -Recurse -Force}
Expand-Archive 'GuanHu_SigProc_Final_Release_20260809.zip' zip_audit -Force
$zd=Get-Item 'zip_audit\SigProcDll-64HF.dll'
if($zd.Length -le 0){throw 'ZIP_EXTRACTED_DLL_EMPTY'}
$zsha=(Get-FileHash $zd.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
if($zsha -ne $env:CAND_SHA){throw "ZIP_EXTRACTED_DLL_SHA_FAIL $zsha"}
$zipsha=(Get-FileHash 'GuanHu_SigProc_Final_Release_20260809.zip' -Algorithm SHA256).Hash.ToLowerInvariant()
@('FINAL_ZIP_AUDIT_PASS',"ZIP_SHA256=$zipsha","EXTRACTED_DLL_SHA256=$zsha","EXTRACTED_DLL_BYTES=$($zd.Length)") | Set-Content FINAL_ZIP_AUDIT_PASS.txt

# G. Durable PASS lock in Git history.
New-Item -ItemType Directory -Force evidence_summary | Out-Null
Copy-Item '87EC_EXACT_NATIVE_AND_COMPLETE_FULLREG_PASS.lock','FINAL_RELEASE_MANIFEST.txt','FINAL_ZIP_AUDIT_PASS.txt','87ec_exact_binding.txt' evidence_summary\ -Force
git config user.name windows-dll-test-bot
git config user.email windows-dll-test-bot@users.noreply.github.com
git add evidence_summary
git commit -m 'Lock authoritative exact 87ec complete native regression PASS'
if($LASTEXITCODE -ne 0){throw 'FINAL_PASS_COMMIT_FAIL'}
git push origin "HEAD:$env:HANDOFF_BRANCH"
if($LASTEXITCODE -ne 0){throw 'FINAL_PASS_PUSH_FAIL'}
'87EC_AUTHORITATIVE_FINAL_RELEASE_GATE_PASS' | Set-Content 87ec_final_gate_pass.txt
