param([Parameter(Mandatory=$true)][ValidateSet('baseline_static','sentinel','full','determinism')][string]$Mode)
$ErrorActionPreference='Stop'
$root=(Get-Location).Path
function Assert-Sha([string]$Path,[string]$Expected,[string]$Name){$h=(Get-FileHash $Path -Algorithm SHA256).Hash.ToLowerInvariant();if($h -ne $Expected){throw "$Name SHA_FAIL $h expected=$Expected"};return $h}
function Mark([string]$Path,[string]$Text){if(-not(Select-String -Path $Path -Pattern $Text -SimpleMatch -Quiet)){throw "MARKER_FAIL $Text in $Path"}}
function Copy-Rt([string]$Src,[string]$Dst){if(Test-Path $Dst){Remove-Item $Dst -Recurse -Force};New-Item -ItemType Directory -Force $Dst|Out-Null;Copy-Item "$Src\*" $Dst -Recurse -Force;return (Resolve-Path $Dst).Path}
function Run-N([string]$Log,[string[]]$RunArgs){& $script:Exe @RunArgs *> $Log;$rc=$LASTEXITCODE;Get-Content $Log;if($rc -ne 0){throw "NATIVE_FAIL rc=$rc $Log"}}

$xz=(Resolve-Path 'checkpoint\c8b8_fullreg_payload_v2.tar.xz').Path
Assert-Sha $xz $env:CHECKPOINT_XZ_SHA 'CHECKPOINT'|Out-Null
New-Item -ItemType Directory -Force xzstage,expanded,payload|Out-Null
7z x -y $xz "-o$root\xzstage"|Out-Null
$tar=Get-ChildItem xzstage -Filter '*.tar'|Select-Object -First 1;if(!$tar){throw 'TAR_MISSING'}
7z x -y $tar.FullName "-o$root\expanded"|Out-Null
$src=(Resolve-Path 'expanded\c8b8_fullreg_payload_v2').Path;Copy-Item "$src\*" payload -Recurse -Force
Assert-Sha 'payload\SigProcDll-64HF.dll' $env:PARENT_SHA 'PARENT'|Out-Null
Assert-Sha 'payload\HostCompat.dll' $env:RAW_HOST_SHA 'RAW_HOST'|Out-Null
Assert-Sha 'payload\C63.dll' $env:C63_SHA 'C63'|Out-Null
Assert-Sha 'payload\fullreg_c8b8.c' $env:HARNESS_SHA 'HARNESS'|Out-Null
$c=@(Get-ChildItem core87 -Recurse -Filter 'SigProcDll-64HF.dll'|Where-Object{(Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -eq $env:CAND_SHA});if($c.Count -ne 1){throw "CAND_COUNT $($c.Count)"}
Copy-Item $c[0].FullName 'payload\SigProcDll-64HF.dll' -Force
$cand=(Resolve-Path 'payload\SigProcDll-64HF.dll').Path;Assert-Sha $cand $env:CAND_SHA 'CAND'|Out-Null
$test=(Resolve-Path 'payload\testdata').Path;$frame=(Resolve-Path 'payload\testdata\inner-bed\02_supine.ghf').Path
$srcC=(Resolve-Path 'payload\fullreg_c8b8.c').Path
cl /nologo /O2 /W4 /D_CRT_SECURE_NO_WARNINGS /Fe:fullreg.exe $srcC *> fullreg_compile.txt;if($LASTEXITCODE -ne 0){Get-Content fullreg_compile.txt;throw 'COMPILE_FAIL'}
$script:Exe=(Resolve-Path 'fullreg.exe').Path

if($Mode -eq 'baseline_static'){
  $raw=(Resolve-Path 'payload\HostCompat.dll').Path
  $fix=Get-ChildItem ba15fixture -Recurse -Filter 'SigProcDll-HostCompat-StackProbeSafe-ba15.dll'|Select-Object -First 1;if(!$fix){throw 'BA15_MISSING'}
  Assert-Sha $fix.FullName $env:BA15_SHA 'BA15'|Out-Null
  Copy-Item $raw 'raw_host.dll' -Force;Copy-Item $fix.FullName 'payload\HostCompat.dll' -Force;$safe=(Resolve-Path 'payload\HostCompat.dll').Path
  $ghf=@(Get-ChildItem payload\testdata -Recurse -Filter '*.ghf');$gb=($ghf|Measure-Object Length -Sum).Sum;if($ghf.Count -ne 13 -or $gb -ne 82484656){throw "GHF_COVERAGE $($ghf.Count) $gb"}
  dumpbin /headers $cand|Out-File cand_headers.txt;dumpbin /exports $cand|Out-File cand_exports.txt;dumpbin /dependents $cand|Out-File cand_deps.txt
  dumpbin /headers $safe|Out-File ba15_headers.txt;dumpbin /exports $safe|Out-File ba15_exports.txt;dumpbin /dependents $safe|Out-File ba15_deps.txt;dumpbin /dependents raw_host.dll|Out-File raw_deps.txt
  Mark cand_headers.txt '14C machine (x86)';Mark ba15_headers.txt '14C machine (x86)'
  foreach($e in @('_SigProc@24','_SigProc_Fini@0','_SigProc_Init@8','_SigProc_Stat@0')){Mark cand_exports.txt $e;Mark ba15_exports.txt $e}
  @'
from pathlib import Path
import re,struct,sys
def deps(p):
 s=Path(p).read_text(errors='ignore');o=set();cap=False
 for l in s.splitlines():
  t=l.strip()
  if t.startswith('Image has the following dependencies'):cap=True;continue
  if cap and re.fullmatch(r'[A-Za-z0-9_.-]+\.dll',t,re.I):o.add(t.lower())
 return o
def bad(p):
 b=Path(p).read_bytes();u16=lambda o:struct.unpack_from('<H',b,o)[0];u32=lambda o:struct.unpack_from('<I',b,o)[0];pe=u32(0x3c);n=u16(pe+6);osz=u16(pe+20);s0=pe+24+osz;z=[]
 for i in range(n):
  o=s0+40*i;rs=u32(o+16);rp=u32(o+20);ch=u32(o+36)
  if ch&0x20000000:
   for x in range(rp,max(rp,rp+rs-6)):
    if b[x:x+2]==b'\x81\xec':
     imm=u32(x+2)
     if 0x1000<=imm<0x100000:z.append((x,imm))
 return z
c=deps('cand_deps.txt');r=deps('raw_deps.txt');s=deps('ba15_deps.txt')
if r!=s:sys.exit('BA15_RAW_IMPORT_MISMATCH')
if c-r:sys.exit('CAND_IMPORT_EXTRA '+repr(sorted(c-r)))
for p in ['payload/SigProcDll-64HF.dll','payload/HostCompat.dll']:
 if bad(p):sys.exit('DIRECT_LARGE_STACK '+p)
b=Path('payload/SigProcDll-64HF.dll').read_bytes();f=Path('payload/HostCompat.dll').read_bytes()
if b'.stkfix' not in b or b'.thrfix' not in b:sys.exit('CAND_SECTION_MARKER')
if b'.stkfix' not in f:sys.exit('BA15_STKFIX_MARKER')
'@|Set-Content -Encoding ascii $env:RUNNER_TEMP\parallel_static.py
  python $env:RUNNER_TEMP\parallel_static.py *> static_python.log;if($LASTEXITCODE -ne 0){Get-Content static_python.log;throw 'STATIC_PY_FAIL'}
  $r1=Copy-Rt 'payload\runtime\inner-bed' 'rt_base_safe';$r2=Copy-Rt 'payload\runtime\inner-bed' 'rt_c63'
  Run-N 'hostcompat_safe.log' @('baseline',$safe,$r1,$frame);Run-N 'c63.log' @('baseline',(Resolve-Path 'payload\C63.dll').Path,$r2,$frame)
  Mark hostcompat_safe.log 'BASELINE_NATIVE_NONZERO_PASS';Mark c63.log 'BASELINE_NATIVE_NONZERO_PASS'
  @('BASELINE_STATIC_PASS',"CAND_SHA=$env:CAND_SHA","BA15_SHA=$env:BA15_SHA",'RAW_HOST_SHA=081c4c62d2bf377913eb2aca0cc3cf3bf656350c8abaa3aaf11d171dac604804','GHF_COUNT=13','GHF_BYTES=82484656','BA15_RAW_IMPORT_EQUAL=PASS','DIRECT_LARGE_STACK=0','BASELINE_FIXTURE_SCOPE=SURVIVABILITY_ONLY')|Set-Content mode_pass.txt
}
elseif($Mode -eq 'sentinel'){
  $rt=Copy-Rt 'payload\runtime\outer-medical-bed' 'rt_sentinel';Run-N 'sentinel.log' @('sentinel',$cand,$rt,$test);Mark sentinel.log 'SEQ_TARGETS_VITAL_SUPPRESSION_RECOVERY_PASS';@('SENTINEL_PASS',"CAND_SHA=$env:CAND_SHA")|Set-Content mode_pass.txt
}
elseif($Mode -eq 'full'){
  $ri=Copy-Rt 'payload\runtime\inner-bed' 'rt_full_i';$ro=Copy-Rt 'payload\runtime\outer-medical-bed' 'rt_full_o';Run-N 'full.log' @('full',$cand,$ri,$ro,$test);Mark full.log 'FULL_GHF_NATIVE_PASS frames=10808 samples=6853006';Mark full.log 'PERFORMANCE_PASS';$p=Select-String -Path full.log -Pattern 'PERFORMANCE_PASS avg_ms=([0-9.]+)'|Select-Object -Last 1;if(!$p){throw 'PERF_LINE'};$avg=[double]$p.Matches[0].Groups[1].Value;if($avg -gt 100){throw "PERF_GT_100 $avg"};@('FULL_13_GHF_PASS',"CAND_SHA=$env:CAND_SHA",'FRAMES=10808','SAMPLES=6853006',"AVG_MS=$avg")|Set-Content mode_pass.txt
}
elseif($Mode -eq 'determinism'){
  $a=Copy-Rt 'payload\runtime\inner-bed' 'rt_d1i';$b=Copy-Rt 'payload\runtime\outer-medical-bed' 'rt_d1o';$c1=Copy-Rt 'payload\runtime\inner-bed' 'rt_d2i';$d=Copy-Rt 'payload\runtime\outer-medical-bed' 'rt_d2o';Run-N 'determinism.log' @('determinism',$cand,$a,$b,$c1,$d,$test);Mark determinism.log 'DETERMINISTIC_REPLAY_PASS';@('DETERMINISM_PASS',"CAND_SHA=$env:CAND_SHA")|Set-Content mode_pass.txt
}
Assert-Sha $cand $env:CAND_SHA 'POST_MODE_CAND'|Out-Null
