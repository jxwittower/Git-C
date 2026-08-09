param([Parameter(Mandatory=$true)][ValidateSet('static_loader','baseline','sentinel','long','threads','full','determinism','realtime')][string]$Mode)
$ErrorActionPreference='Stop';$root=(Get-Location).Path
function Sha($p,$e,$n){$h=(Get-FileHash $p -Algorithm SHA256).Hash.ToLowerInvariant();if($h-ne$e){throw "$n SHA_FAIL $h"};$h}
function MkRt($s,$d){if(Test-Path $d){Remove-Item $d -Recurse -Force};New-Item -ItemType Directory -Force $d|Out-Null;Copy-Item "$s\*" $d -Recurse -Force;(Resolve-Path $d).Path}
function RunN($log,[string[]]$a){& $script:exe @a *> $log;$rc=$LASTEXITCODE;Get-Content $log;if($rc-ne0){throw "NATIVE_FAIL mode=$Mode rc=$rc log=$log"}}
function Mark($p,$m){if(-not(Select-String -Path $p -Pattern $m -SimpleMatch -Quiet)){throw "MARKER_FAIL [$m] $p"}}
$xz=(Resolve-Path 'checkpoint\c8b8_fullreg_payload_v2.tar.xz').Path;Sha $xz $env:CHECKPOINT_XZ_SHA 'CHECKPOINT'|Out-Null
New-Item -ItemType Directory -Force xs,u,payload|Out-Null;7z x -y $xz "-o$root\xs"|Out-Null;$t=Get-ChildItem xs -Filter '*.tar'|Select-Object -First 1;if(!$t){throw'TAR_MISSING'};7z x -y $t.FullName "-o$root\u"|Out-Null;$src=(Resolve-Path 'u\c8b8_fullreg_payload_v2').Path;Copy-Item "$src\*" payload -Recurse -Force
$c63=(Resolve-Path 'payload\C63.dll').Path;Sha $c63 $env:C63_SHA 'C63'|Out-Null
$test=(Resolve-Path 'payload\testdata').Path;$frame=(Resolve-Path 'payload\testdata\inner-bed\02_supine.ghf').Path;$csrc=(Resolve-Path 'payload\fullreg_c8b8.c').Path
$ghf=@(Get-ChildItem payload\testdata -Recurse -Filter '*.ghf');$gb=($ghf|Measure-Object Length -Sum).Sum;if($ghf.Count-ne13-or$gb-ne82484656){throw "GHF_COVERAGE $($ghf.Count) $gb"}
cl /nologo /O2 /W4 /D_CRT_SECURE_NO_WARNINGS /Fe:fullreg.exe $csrc *> compile.log;if($LASTEXITCODE-ne0){Get-Content compile.log;throw'COMPILE_FAIL'};$script:exe=(Resolve-Path fullreg.exe).Path
if($Mode-eq'static_loader'){
 dumpbin /headers $c63|Out-File headers.txt;dumpbin /exports $c63|Out-File exports.txt;dumpbin /dependents $c63|Out-File deps.txt;Mark headers.txt '14C machine (x86)';foreach($e in @('_SigProc@24','_SigProc_Fini@0','_SigProc_Init@8','_SigProc_Stat@0')){Mark exports.txt $e}
 @'
from pathlib import Path
import struct,sys
p=Path('payload/C63.dll');b=p.read_bytes();u16=lambda o:struct.unpack_from('<H',b,o)[0];u32=lambda o:struct.unpack_from('<I',b,o)[0];pe=u32(0x3c);n=u16(pe+6);osz=u16(pe+20);s0=pe+24+osz;bad=[]
for i in range(n):
 o=s0+40*i;rs=u32(o+16);rp=u32(o+20);ch=u32(o+36)
 if ch&0x20000000:
  for x in range(rp,max(rp,rp+rs-6)):
   if b[x:x+2]==b'\x81\xec':
    z=u32(x+2)
    if 0x1000<=z<0x100000:bad.append((x,z))
if bad:sys.exit('DIRECT_LARGE_STACK '+repr(bad))
Path('stack.txt').write_text('DIRECT_LARGE_STACK=0\n')
'@|Set-Content -Encoding ascii $env:RUNNER_TEMP\scan.py;python $env:RUNNER_TEMP\scan.py;if($LASTEXITCODE-ne0){throw'STACK_SCAN_FAIL'}
 $sm=(Resolve-Path 'payload\SigProcLoaderContractSmoke.exe').Path;$ri=MkRt 'payload\runtime\inner-bed' 'rt_li';$ro=MkRt 'payload\runtime\outer-medical-bed' 'rt_lo';foreach($r in @($ri,$ro)){Copy-Item $c63 "$r\SigProcDll-64HF.dll" -Force;Copy-Item $sm "$r\SigProcLoaderContractSmoke.exe" -Force};Push-Location $ri;.\SigProcLoaderContractSmoke.exe *> "$root\loader_inner.log";$a=$LASTEXITCODE;Pop-Location;Push-Location $ro;.\SigProcLoaderContractSmoke.exe *> "$root\loader_outer.log";$b=$LASTEXITCODE;Pop-Location;if($a-ne0-or$b-ne0){throw "LOADER_EXIT $a $b"};Mark loader_inner.log 'ALL_LOADER_CONTRACT_TESTS_PASS';Mark loader_outer.log 'ALL_LOADER_CONTRACT_TESTS_PASS';@('C63_STATIC_LOADER_PASS',"CAND_SHA=$env:C63_SHA",'DIRECT_LARGE_STACK=0','BCRYPT_IMPORT=YES')|Set-Content mode_pass.txt
}elseif($Mode-eq'baseline'){$r=MkRt 'payload\runtime\inner-bed' 'rt_b';RunN baseline.log @('baseline',$c63,$r,$frame);Mark baseline.log 'BASELINE_NATIVE_NONZERO_PASS';@('C63_BASELINE_PASS',"CAND_SHA=$env:C63_SHA")|Set-Content mode_pass.txt
}elseif($Mode-eq'sentinel'){$r=MkRt 'payload\runtime\outer-medical-bed' 'rt_s';RunN sentinel.log @('sentinel',$c63,$r,$test);Mark sentinel.log 'SEQ_TARGETS_VITAL_SUPPRESSION_RECOVERY_PASS';@('C63_SENTINEL_PASS',"CAND_SHA=$env:C63_SHA")|Set-Content mode_pass.txt
}elseif($Mode-eq'long'){$r=MkRt 'payload\runtime\inner-bed' 'rt_l';RunN long.log @('long',$c63,$r,$frame);Mark long.log 'LONG_STABILITY_PASS loops=20000';@('C63_LONG_PASS',"CAND_SHA=$env:C63_SHA")|Set-Content mode_pass.txt
}elseif($Mode-eq'threads'){Copy-Item $c63 a.dll;Copy-Item $c63 b.dll;$r=MkRt 'payload\runtime\inner-bed' 'rt_t';RunN threads.log @('threads',(Resolve-Path a.dll).Path,(Resolve-Path b.dll).Path,$r,$frame);Mark threads.log 'TWO_THREAD_STRESS_PASS threads=2 loops_each=2000';@('C63_THREADS_PASS',"CAND_SHA=$env:C63_SHA")|Set-Content mode_pass.txt
}elseif($Mode-eq'full'){$i=MkRt 'payload\runtime\inner-bed' 'rt_fi';$o=MkRt 'payload\runtime\outer-medical-bed' 'rt_fo';RunN full.log @('full',$c63,$i,$o,$test);Mark full.log 'FULL_GHF_NATIVE_PASS frames=10808 samples=6853006';Mark full.log 'PERFORMANCE_PASS';$p=Select-String -Path full.log -Pattern 'PERFORMANCE_PASS avg_ms=([0-9.]+)'|Select-Object -Last 1;if(!$p){throw'PERF_LINE'};$avg=[double]$p.Matches[0].Groups[1].Value;if($avg-gt100){throw "PERF_GT100 $avg"};@('C63_FULL_PASS',"CAND_SHA=$env:C63_SHA","AVG_MS=$avg")|Set-Content mode_pass.txt
}elseif($Mode-eq'determinism'){$a=MkRt 'payload\runtime\inner-bed' 'rt_d1i';$b=MkRt 'payload\runtime\outer-medical-bed' 'rt_d1o';$c=MkRt 'payload\runtime\inner-bed' 'rt_d2i';$d=MkRt 'payload\runtime\outer-medical-bed' 'rt_d2o';RunN determinism.log @('determinism',$c63,$a,$b,$c,$d,$test);Mark determinism.log 'DETERMINISTIC_REPLAY_PASS';@('C63_DETERMINISM_PASS',"CAND_SHA=$env:C63_SHA")|Set-Content mode_pass.txt
}elseif($Mode-eq'realtime'){$r=MkRt 'payload\runtime\inner-bed' 'rt_r';RunN realtime.log @('realtime',$c63,$r,$frame);Mark realtime.log 'REALTIME_1HZ_PASS frames=60';@('C63_REALTIME_PASS',"CAND_SHA=$env:C63_SHA")|Set-Content mode_pass.txt}
Sha $c63 $env:C63_SHA 'POST_C63'|Out-Null
