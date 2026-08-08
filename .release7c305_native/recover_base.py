from pathlib import Path
import os,subprocess,hashlib,shutil,tarfile,zipfile,lzma,sys
T=Path(os.environ['RUNNER_TEMP']); E=T/'p9.enc'; BAD=os.environ['BAD_SHA']
C=[]
for x in (T/'candidates.txt').read_text(errors='ignore').splitlines():
    x=x.strip()
    if x and x not in C:C.append(x)
def H(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def X(src,dst):
    shutil.rmtree(dst,ignore_errors=True);dst.mkdir()
    try:
        if zipfile.is_zipfile(src):zipfile.ZipFile(src).extractall(dst);return 1
    except:pass
    try:
        if tarfile.is_tarfile(src):tarfile.open(src).extractall(dst);return 1
    except:pass
    try:
        raw=lzma.decompress(src.read_bytes());q=dst/'i';q.write_bytes(raw)
        if tarfile.is_tarfile(q):tarfile.open(q).extractall(dst/'x');return 1
        if zipfile.is_zipfile(q):zipfile.ZipFile(q).extractall(dst/'x');return 1
    except:pass
    return 0
for ci,pw in enumerate(C):
    pf=T/'pw';pf.write_text(pw)
    for it in (200000,250000,100000,150000,300000,600000):
        d=T/'dec';r=subprocess.run(['openssl','enc','-d','-aes-256-cbc','-pbkdf2','-iter',str(it),'-md','sha256','-in',str(E),'-out',str(d),'-pass',f'file:{pf}'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if r.returncode:continue
        z=Path('p9_try')
        if not X(d,z):continue
        for p in z.rglob('*.dll'):
            if H(p)==BAD:
                Path('native_stage').mkdir(exist_ok=True);shutil.copy2(p,'native_stage/base66a44.dll');Path('p9_recovery.txt').write_text(f'INDEX={ci}\nITER={it}\nBASE_SHA={BAD}\n');print('EXACT_66A_BASE_RECOVERED');sys.exit(0)
sys.exit('NO_EXACT_66A_BASE')
