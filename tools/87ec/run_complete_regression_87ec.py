from __future__ import annotations
import csv, hashlib, shutil, statistics, subprocess, sys
from pathlib import Path
ROOT=Path(sys.argv[1]).resolve(); HOST=Path(sys.argv[2]).resolve(); OUT=Path(sys.argv[3]).resolve(); OUT.mkdir(parents=True, exist_ok=True)
CAND=ROOT/'SigProcDll-64HF.dll'; HC=ROOT/'HostCompat_stackprobe.dll'; C63=ROOT/'C63.dll'; TD=ROOT/'testdata'; RT=ROOT/'runtime'
INNER=[TD/'inner-bed'/x for x in ['01_initial_empty.ghf','02_supine.ghf','03_left.ghf','04_right.ghf','05_free.ghf','06_final_empty.ghf']]
OUTER=[TD/'outer-medical-bed'/x for x in ['01_initial_empty.ghf','02_supine.ghf','03_left.ghf','04_right.ghf','05_leave.ghf','06_return_free.ghf','07_final_empty.ghf']]
EXPECTED={'SigProcDll-64HF.dll':'87ec3f9f2748d3143136c97e652b0334d63b973338b4c802aaea08e853ad226e','HostCompat.dll':'081c4c62d2bf377913eb2aca0cc3cf3bf656350c8abaa3aaf11d171dac604804','C63.dll':'56c02d18a9ee68a7ae14c4601e4ba24f7af170c6db01ea21fbff91cbe6b082fb','SigProcLoaderContractSmoke.exe':'a9cc5cf614114c9481073669a3fd5d7ef5e1a1adce7e0fdc3f62824e0d50431d','HostCompat_stackprobe.dll':'ba15a5b0d4755597892ab6d20b0f9eeb49d5ac5da9dfd97ed6e94ecff7aac13b'}
INVALID=65535
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
for n,h in EXPECTED.items():
 p=ROOT/n
 if sha(p)!=h:raise SystemExit(f'HASH_FAIL {n} {sha(p)}')
print('EXACT_BINARY_SHA_BINDING_PASS');print('HOSTCOMPAT_STACKPROBE_BASELINE_BINDING_PASS')
def fresh(kind,tag):
 d=OUT/f'rt_{tag}_{kind}'
 if d.exists():shutil.rmtree(d)
 shutil.copytree(RT/kind,d);return d
def run(args,log):
 p=subprocess.run([str(x) for x in args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace');(OUT/log).write_text(p.stdout,encoding='utf-8');print(p.stdout,end='')
 if p.returncode:raise SystemExit(f'CMD_FAIL rc={p.returncode} log={log}')
 return p.stdout
def replay(dll,kind,files,tag):
 rt=fresh(kind,tag);csvp=OUT/f'{tag}.csv';run([HOST,'replay',dll,rt,csvp,*files],f'{tag}.log')
 with open(csvp,newline='') as f:return list(csv.DictReader(f)),csvp
def ints(rows):
 for r in rows:
  for k in ('source','row','seq','main','hr','rr','heart_status','resp_status','checksum'):r[k]=int(r[k])
 return rows
def valid(v):return 0 < v < INVALID
ci1,p1=replay(CAND,'inner-bed',INNER,'cand_inner_1');ci2,p2=replay(CAND,'inner-bed',INNER,'cand_inner_2')
if p1.read_bytes()!=p2.read_bytes():raise SystemExit('DETERMINISTIC_REPLAY_FAIL_INNER')
co1,p3=replay(CAND,'outer-medical-bed',OUTER,'cand_outer_1');co2,p4=replay(CAND,'outer-medical-bed',OUTER,'cand_outer_2')
if p3.read_bytes()!=p4.read_bytes():raise SystemExit('DETERMINISTIC_REPLAY_FAIL_OUTER')
print('DETERMINISTIC_REPLAY_PASS');ci=ints(ci1);co=ints(co1)
def tail(rows,src,n=5):return [r for r in rows if r['source']==src][-n:]
def require(cond,msg):
 if not cond:raise SystemExit(msg)
for r in tail(ci,0)+tail(ci,5)+tail(co,0)+tail(co,6):
 require(r['main']==0,'FINAL_EMPTY_STATE_FAIL');require(r['hr']==INVALID and r['rr']==INVALID,'FINAL_EMPTY_VITAL_FAIL')
warn=[r for r in co if r['source']==4 and r['main']==8];require(len(warn)>0,'DEPARTURE_WARNING_STATE8_MISSING');require(all(r['hr']==INVALID and r['rr']==INVALID for r in warn),'WARNING_VITAL_SUPPRESSION_FAIL')
ret=[r for r in co if r['source']==5];require(any(r['main'] not in (0,8) for r in ret),'RETURN_OCCUPANCY_RECOVERY_FAIL');require(any((valid(r['hr']) or valid(r['rr'])) for r in ret[len(ret)//2:]),'RETURN_VITAL_RECOVERY_FAIL')
occ=[r for r in ci if r['source'] in (1,2,3,4)];require(any(r['main'] not in (0,8) for r in occ),'INNER_OCCUPIED_STATE_MISSING');require(any(valid(r['hr']) for r in occ) and any(valid(r['rr']) for r in occ),'INNER_VITALS_MISSING');print('SEQ_TARGETS_VITAL_SUPPRESSION_RECOVERY_PASS')
hi,_=replay(HC,'inner-bed',INNER,'host_inner');ho,_=replay(HC,'outer-medical-bed',OUTER,'host_outer');ci63,_=replay(C63,'inner-bed',INNER,'c63_inner');co63,_=replay(C63,'outer-medical-bed',OUTER,'c63_outer');hi=ints(hi);ho=ints(ho);ci63=ints(ci63);co63=ints(co63)
def vital_compare(a,b,name):
 bm={(r['source'],r['row']):r for r in b};dh=[];dr=[]
 for r in a:
  q=bm.get((r['source'],r['row']))
  if q and r['main'] not in (0,8) and q['main'] not in (0,8):
   if valid(r['hr']) and valid(q['hr']):dh.append(abs(r['hr']-q['hr']))
   if valid(r['rr']) and valid(q['rr']):dr.append(abs(r['rr']-q['rr']))
 require(len(dh)>=10 and len(dr)>=10,f'{name}_COMMON_VITAL_ROWS_TOO_FEW');mh=statistics.median(dh);mr=statistics.median(dr);require(mh<=15 and mr<=8,f'{name}_VITAL_PARITY_FAIL hr={mh} rr={mr}');print(f'{name}_VITAL_PARITY_PASS common_hr={len(dh)} common_rr={len(dr)} median_hr_diff={mh} median_rr_diff={mr}')
vital_compare(ci,hi,'HOSTCOMPAT_INNER');vital_compare(co,ho,'HOSTCOMPAT_OUTER');vital_compare(ci,ci63,'C63_INNER');vital_compare(co,co63,'C63_OUTER');print('C63_HOSTCOMPAT_COMPARISON_PASS')
sup=INNER[1];out=run([HOST,'stress',CAND,fresh('inner-bed','stress'),sup,'20000'],'long_stability.log')
if 'LONG_STABILITY_PASS loops=20000' not in out:raise SystemExit('LONG_STABILITY_MARKER_FAIL')
out=run([HOST,'threadstress',CAND,fresh('inner-bed','thread'),sup,'2000'],'thread_stress.log')
if 'TWO_THREAD_STRESS_PASS threads=2 loops_each=2000' not in out:raise SystemExit('THREAD_STRESS_MARKER_FAIL')
out=run([HOST,'realtime',CAND,fresh('inner-bed','realtime'),sup,'60'],'realtime_1hz.log')
if 'REALTIME_1HZ_PASS frames=60' not in out:raise SystemExit('REALTIME_MARKER_FAIL')
print('FULL_DATA_PERFORMANCE_PASS');print('PERFORMANCE_AND_STABILITY_PASS');print('COMPLETE_NATIVE_WINDOWS_REGRESSION_PASS')
