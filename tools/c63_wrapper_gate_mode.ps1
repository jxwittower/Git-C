param([Parameter(Mandatory=$true)][ValidateSet('static_loader','baseline','sentinel','long','threads','full','determinism','realtime')][string]$Mode)
$ErrorActionPreference='Stop';$root=(Get-Location).Path
function Sha($p,$e,$n){$h=(Get-FileHash $p -Algorithm SHA256).Hash.ToLowerInvariant();if($e -and $h-ne$e){throw "$n SHA_FAIL $h expected=$e"};return $h}
function MkRt($s,$d){if(Test-Path $d){Remove-Item $d -Recurse -Force};New-Item -ItemType Directory -Force $d|Out-Null;Copy-Item "$s\*" $d -Recurse -Force;return (Resolve-Path $d).Path}
function RunN($log,[string[]]$a){& $script:exe @a *> $log;$rc=$LASTEXITCODE;Get-Content $log;if($rc-ne0){throw "NATIVE_FAIL mode=$Mode rc=$rc log=$log args=$($a -join ' | ')"}}
function Mark($p,$m){if(-not(Select-String -Path $p -Pattern $m -SimpleMatch -Quiet)){throw "MARKER_FAIL [$m] $p"}}

# Recover immutable real-data checkpoint.
$xz=(Resolve-Path 'checkpoint\c8b8_fullreg_payload_v2.tar.xz').Path;Sha $xz $env:CHECKPOINT_XZ_SHA 'CHECKPOINT'|Out-Null
New-Item -ItemType Directory -Force xs,u,payload|Out-Null;7z x -y $xz "-o$root\xs"|Out-Null;$t=Get-ChildItem xs -Filter '*.tar'|Select-Object -First 1;if(!$t){throw'TAR_MISSING'};7z x -y $t.FullName "-o$root\u"|Out-Null;$src=(Resolve-Path 'u\c8b8_fullreg_payload_v2').Path;Copy-Item "$src\*" payload -Recurse -Force

$wrapper=(Resolve-Path 'candidate\SigProcDll-64HF.dll').Path;$core=(Resolve-Path 'candidate\SigProcDll-64HF.core.dll').Path
$wrapperSha=Sha $wrapper $env:WRAPPER_SHA 'WRAPPER';Sha $core $env:C63_SHA 'C63_CORE'|Out-Null
Copy-Item $wrapper 'payload\SigProcDll-64HF.dll' -Force;Copy-Item $core 'payload\SigProcDll-64HF.core.dll' -Force
$pub=(Resolve-Path 'payload\SigProcDll-64HF.dll').Path;$coreBound=(Resolve-Path 'payload\SigProcDll-64HF.core.dll').Path
$test=(Resolve-Path 'payload\testdata').Path;$frame=(Resolve-Path 'payload\testdata\inner-bed\02_supine.ghf').Path;$csrc=(Resolve-Path 'payload\fullreg_c8b8.c').Path
$ghf=@(Get-ChildItem payload\testdata -Recurse -Filter '*.ghf');$gb=($ghf|Measure-Object Length -Sum).Sum;if($ghf.Count-ne13-or$gb-ne82484656){throw "GHF_COVERAGE $($ghf.Count) $gb"}
cl /nologo /O2 /W4 /D_CRT_SECURE_NO_WARNINGS /Fe:fullreg.exe $csrc *> compile.log;if($LASTEXITCODE-ne0){Get-Content compile.log;throw'COMPILE_FAIL'};$script:exe=(Resolve-Path fullreg.exe).Path

if($Mode-eq'static_loader'){
 dumpbin /headers $pub|Out-File headers.txt;dumpbin /exports $pub|Out-File exports.txt;dumpbin /dependents $pub|Out-File deps.txt;dumpbin /dependents $coreBound|Out-File core_deps.txt
 Mark headers.txt '14C machine (x86)';foreach($e in @('_SigProc@24','_SigProc_Fini@0','_SigProc_Init@8','_SigProc_Stat@0')){Mark exports.txt $e}
 @'
from pathlib import Path
import re,struct,sys

def bad(p):
 b=Path(p).read_bytes();u16=lambda o:struct.unpack_from('<H',b,o)[0];u32=lambda o:struct.unpack_from('<I',b,o)[0];pe=u32(0x3c);n=u16(pe+6);osz=u16(pe+20);s0=pe+24+osz;z=[]
 for i in range(n):
  o=s0+40*i;rs=u32(o+16);rp=u32(o+20);ch=u32(o+36)
  if ch&0x20000000:
   for x in range(rp,max(rp,rp+rs-6)):
    if b[x:x+2]==b'\x81\xec':
     v=u32(x+2)
     if 0x1000<=v<0x100000:z.append((x,v))
 return z
for p in ['payload/SigProcDll-64HF.dll','payload/SigProcDll-64HF.core.dll']:
 z=bad(p)
 if z:sys.exit('DIRECT_LARGE_STACK '+p+' '+repr(z))
Path('stack_gate.txt').write_text('WRAPPER_AND_CORE_DIRECT_LARGE_STACK=0\n')
'@|Set-Content -Encoding ascii $env:RUNNER_TEMP\scan.py;python $env:RUNNER_TEMP\scan.py;if($LASTEXITCODE-ne0){throw'STACK_SCAN_FAIL'}
 $sm=(Resolve-Path 'payload\SigProcLoaderContractSmoke.exe').Path;$ri=MkRt 'payload\runtime\inner-bed' 'rt_li';$ro=MkRt 'payload\runtime\outer-medical-bed' 'rt_lo';foreach($r in @($ri,$ro)){Copy-Item $pub "$r\SigProcDll-64HF.dll" -Force;Copy-Item $coreBound "$r\SigProcDll-64HF.core.dll" -Force;Copy-Item $sm "$r\SigProcLoaderContractSmoke.exe" -Force};Push-Location $ri;.\SigProcLoaderContractSmoke.exe *> "$root\loader_inner.log";$a=$LASTEXITCODE;Pop-Location;Push-Location $ro;.\SigProcLoaderContractSmoke.exe *> "$root\loader_outer.log";$b=$LASTEXITCODE;Pop-Location;if($a-ne0-or$b-ne0){throw "LOADER_EXIT $a $b"};Mark loader_inner.log 'ALL_LOADER_CONTRACT_TESTS_PASS';Mark loader_outer.log 'ALL_LOADER_CONTRACT_TESTS_PASS';@('WRAPPER_STATIC_LOADER_PASS',"CAND_SHA=$wrapperSha",'CORE_SHA=56c02d18a9ee68a7ae14c4601e4ba24f7af170c6db01ea21fbff91cbe6b082fb','DIRECT_LARGE_STACK=0')|Set-Content mode_pass.txt
}elseif($Mode-eq'baseline'){$r=MkRt 'payload\runtime\inner-bed' 'rt_b';RunN baseline.log @('baseline',$pub,$r,$frame);Mark baseline.log 'BASELINE_NATIVE_NONZERO_PASS';@('WRAPPER_BASELINE_PASS',"CAND_SHA=$wrapperSha")|Set-Content mode_pass.txt
}elseif($Mode-eq'sentinel'){$r=MkRt 'payload\runtime\outer-medical-bed' 'rt_s';RunN sentinel.log @('sentinel',$pub,$r,$test);Mark sentinel.log 'SEQ_TARGETS_VITAL_SUPPRESSION_RECOVERY_PASS';@('WRAPPER_SENTINEL_PASS',"CAND_SHA=$wrapperSha")|Set-Content mode_pass.txt
}elseif($Mode-eq'long'){$r=MkRt 'payload\runtime\inner-bed' 'rt_l';RunN long.log @('long',$pub,$r,$frame);Mark long.log 'LONG_STABILITY_PASS loops=20000';@('WRAPPER_LONG_PASS',"CAND_SHA=$wrapperSha")|Set-Content mode_pass.txt
}elseif($Mode-eq'threads'){
 Copy-Item $pub a.dll;Copy-Item $pub b.dll;Copy-Item $coreBound a.core.dll;Copy-Item $coreBound b.core.dll;$r=MkRt 'payload\runtime\inner-bed' 'rt_t';RunN threads.log @('threads',(Resolve-Path a.dll).Path,(Resolve-Path b.dll).Path,$r,$frame);Mark threads.log 'TWO_THREAD_STRESS_PASS threads=2 loops_each=2000';@('WRAPPER_THREADS_PASS',"CAND_SHA=$wrapperSha")|Set-Content mode_pass.txt
}elseif($Mode-eq'full'){$i=MkRt 'payload\runtime\inner-bed' 'rt_fi';$o=MkRt 'payload\runtime\outer-medical-bed' 'rt_fo';RunN full.log @('full',$pub,$i,$o,$test);Mark full.log 'FULL_GHF_NATIVE_PASS frames=10808 samples=6853006';Mark full.log 'PERFORMANCE_PASS';$p=Select-String -Path full.log -Pattern 'PERFORMANCE_PASS avg_ms=([0-9.]+)'|Select-Object -Last 1;if(!$p){throw'PERF_LINE'};$avg=[double]$p.Matches[0].Groups[1].Value;if($avg-gt100){throw "PERF_GT100 $avg"};@('WRAPPER_FULL_PASS',"CAND_SHA=$wrapperSha","AVG_MS=$avg")|Set-Content mode_pass.txt
}elseif($Mode-eq'determinism'){$a=MkRt 'payload\runtime\inner-bed' 'rt_d1i';$b=MkRt 'payload\runtime\outer-medical-bed' 'rt_d1o';$c=MkRt 'payload\runtime\inner-bed' 'rt_d2i';$d=MkRt 'payload\runtime\outer-medical-bed' 'rt_d2o';RunN determinism.log @('determinism',$pub,$a,$b,$c,$d,$test);Mark determinism.log 'DETERMINISTIC_REPLAY_PASS';@('WRAPPER_DETERMINISM_PASS',"CAND_SHA=$wrapperSha")|Set-Content mode_pass.txt
}elseif($Mode-eq'realtime'){$r=MkRt 'payload\runtime\inner-bed' 'rt_r';RunN realtime.log @('realtime',$pub,$r,$frame);Mark realtime.log 'REALTIME_1HZ_PASS frames=60';@('WRAPPER_REALTIME_PASS',"CAND_SHA=$wrapperSha")|Set-Content mode_pass.txt}
Sha $pub $env:WRAPPER_SHA 'POST_WRAPPER'|Out-Null;Sha $coreBound $env:C63_SHA 'POST_CORE'|Out-Null
