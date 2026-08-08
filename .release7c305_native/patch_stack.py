from pathlib import Path
import os,struct,hashlib,sys
b=bytearray(Path('native_stage/base66a44.dll').read_bytes());BAD=os.environ['BAD_SHA'];FIX=os.environ['FIX_SHA']
if hashlib.sha256(b).hexdigest()!=BAD:sys.exit('BAD_BASE')
u16=lambda o:struct.unpack_from('<H',b,o)[0];u32=lambda o:struct.unpack_from('<I',b,o)[0]
def p16(o,v):struct.pack_into('<H',b,o,v)
def p32(o,v):struct.pack_into('<I',b,o,v)
A=lambda x,a:(x+a-1)//a*a;pe=u32(0x3c);n=u16(pe+6);osz=u16(pe+20);opt=pe+24;s0=opt+osz;sa=u32(opt+32);fa=u32(opt+36);sh=u32(opt+60);sec=[]
for i in range(n):
    o=s0+40*i;sec.append((u32(o+8),u32(o+12),u32(o+16),u32(o+20),u32(o+36),o))
vs,tva,trs,trp,_,_=max((s for s in sec if s[4]&0x20000000),key=lambda s:s[2]);sites=[]
for x in range(trp,trp+trs-6):
    if b[x:x+2]==b'\x81\xec':
        z=u32(x+2)
        if 0x1000<=z<0x100000:sites.append((x,tva+x-trp,z))
if len(sites)!=12:sys.exit(f'SITES={len(sites)}')
chk=bytearray(b'\x51\x8d\x4c\x24\x04\x29\xc1\x19\xc0\xf7\xd0\x21\xc1\x89\xe0\x25\x00\xf0\xff\xff');loop=len(chk);chk+=b'\x39\xc1\x72\x00';jb=len(chk)-1;chk+=b'\x89\xc8\x59\x94\x8b\x00\x89\x04\x24\xc3';probe=len(chk);chk+=b'\x2d\x00\x10\x00\x00\x85\x00\xeb\x00';jm=len(chk)-1;chk[jb]=(probe-jb-1)&255;chk[jm]=(loop-jm-1)&255
nh=s0+40*n;rp=A(max(s[3]+s[2] for s in sec),fa);va=A(max(s[1]+max(s[0],s[2]) for s in sec),sa);pay=bytearray(b'\x90'*120)+chk;rs=A(len(pay),fa)
if nh+40>sh:sys.exit('NO_HDR')
b.extend(b'\0'*max(0,rp+rs-len(b)));b[rp:rp+len(pay)]=pay;cr=va+120
for i,(x,r,z) in enumerate(sites):
    tr=va+10*i;to=rp+10*i;b[to]=0xb8;struct.pack_into('<I',b,to+1,z);b[to+5]=0xe9;struct.pack_into('<i',b,to+6,cr-(tr+10));b[x]=0xe8;struct.pack_into('<i',b,x+1,tr-(r+5));b[x+5]=0x90
b[nh:nh+8]=b'.stkfix\0';p32(nh+8,len(pay));p32(nh+12,va);p32(nh+16,rs);p32(nh+20,rp);p32(nh+24,0);p32(nh+28,0);p16(nh+32,0);p16(nh+34,0);p32(nh+36,0x60000020);p16(pe+6,n+1);p32(opt+56,A(va+len(pay),sa));p32(opt+64,0)
Path('native_stage/SigProcDll-64HF.dll').write_bytes(b);h=hashlib.sha256(b).hexdigest();Path('stackfix.txt').write_text(f'SHA={h}\nSITES=12\n');print(h)
if h!=FIX:sys.exit('FIX_SHA_MISMATCH')
