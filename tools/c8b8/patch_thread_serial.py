from pathlib import Path
import argparse, struct, hashlib, json


def align(x,a): return (x+a-1)//a*a

def patch(inp: Path, out: Path, report: Path|None=None):
    b=bytearray(inp.read_bytes())
    in_sha=hashlib.sha256(b).hexdigest()
    u16=lambda o:struct.unpack_from('<H',b,o)[0]
    u32=lambda o:struct.unpack_from('<I',b,o)[0]
    def p16(o,v): struct.pack_into('<H',b,o,v)
    def p32(o,v): struct.pack_into('<I',b,o,v)
    pe=u32(0x3c)
    if b[pe:pe+4]!=b'PE\0\0': raise SystemExit('NOT_PE')
    n=u16(pe+6); optsz=u16(pe+20); opt=pe+24
    if u16(opt)!=0x10b: raise SystemExit('NOT_PE32')
    image_base=u32(opt+28); sa=u32(opt+32); fa=u32(opt+36); size_headers=u32(opt+60)
    s0=opt+optsz
    secs=[]
    for i in range(n):
        o=s0+40*i
        name=bytes(b[o:o+8]).split(b'\0',1)[0].decode('ascii','replace')
        vs=u32(o+8); va=u32(o+12); rs=u32(o+16); rp=u32(o+20); ch=u32(o+36)
        secs.append({'name':name,'vs':vs,'va':va,'rs':rs,'rp':rp,'ch':ch,'hdr':o})
    def rva_to_off(rva):
        for s in secs:
            span=max(s['vs'],s['rs'])
            if s['va']<=rva<s['va']+span:
                return s['rp']+(rva-s['va'])
        raise ValueError(f'RVA not mapped {rva:x}')
    exp_rva=u32(opt+96); exp_off=rva_to_off(exp_rva)
    num_funcs=u32(exp_off+20); num_names=u32(exp_off+24)
    eat_rva=u32(exp_off+28); npt_rva=u32(exp_off+32); ord_rva=u32(exp_off+36)
    eat_off=rva_to_off(eat_rva); npt_off=rva_to_off(npt_rva); ord_off=rva_to_off(ord_rva)
    exports={}
    for i in range(num_names):
        nrva=u32(npt_off+4*i); noff=rva_to_off(nrva)
        end=b.index(0,noff); name=bytes(b[noff:end]).decode('ascii')
        ordidx=u16(ord_off+2*i)
        if ordidx>=num_funcs: raise SystemExit('BAD_ORD')
        frva=u32(eat_off+4*ordidx)
        exports[name]={'ordidx':ordidx,'rva':frva,'eat_off':eat_off+4*ordidx}
    wanted={'_SigProc@24':24,'_SigProc_Init@8':8,'_SigProc_Stat@0':0,'_SigProc_Fini@0':0}
    for k in wanted:
        if k not in exports: raise SystemExit(f'MISSING_EXPORT {k}')
    newhdr=s0+40*n
    if newhdr+40>size_headers: raise SystemExit('NO_SECTION_HEADER_SLACK')
    max_raw=max(s['rp']+s['rs'] for s in secs if s['rs'])
    max_va=max(s['va']+max(s['vs'],s['rs']) for s in secs)
    rp=align(max_raw,fa); va=align(max_va,sa)
    code=bytearray(b'\x90'*0x180)
    lock_off=0x180
    code += b'\x00\x00\x00\x00'
    wrappers={}
    cursor=0
    for name,argbytes in wanted.items():
        orig=exports[name]['rva']; start=cursor
        w=bytearray()
        w += b'\x55\x8b\xec\x53\x56'
        callpos=len(w); w += b'\xe8\x00\x00\x00\x00'
        w += b'\x5e'
        pop_rva=va+start+callpos+5
        delta=(va+lock_off)-pop_rva
        w += b'\x81\xc6'+struct.pack('<i',delta)
        w += b'\xba\x01\x00\x00\x00'
        spin=len(w)
        w += b'\x31\xc0'
        w += b'\xf0\x0f\xb1\x16'
        rel=(spin-(len(w)+2)) & 0xff
        w += b'\x75'+bytes([rel])
        for off in range(8+argbytes-4,7,-4):
            if -128<=off<=127: w += b'\xff\x75'+bytes([off & 0xff])
            else: w += b'\xff\xb5'+struct.pack('<i',off)
        cpos=len(w); w += b'\xe8\x00\x00\x00\x00'
        next_rva=va+start+cpos+5
        struct.pack_into('<i',w,cpos+1,orig-next_rva)
        w += b'\x8b\xd8'
        w += b'\xc7\x06\x00\x00\x00\x00'
        w += b'\x8b\xc3\x5e\x5b\x8b\xe5\x5d'
        w += b'\xc2'+struct.pack('<H',argbytes)
        end=start+len(w)
        if end>lock_off: raise SystemExit('WRAPPERS_TOO_BIG')
        code[start:end]=w
        wrappers[name]={'orig_rva':orig,'wrapper_rva':va+start,'argbytes':argbytes,'size':len(w)}
        cursor=align(end,16)
    rawsz=align(len(code),fa)
    b.extend(b'\0'*max(0,rp+rawsz-len(b)))
    b[rp:rp+len(code)]=code
    b[newhdr:newhdr+8]=b'.thrfix\0'
    p32(newhdr+8,len(code)); p32(newhdr+12,va); p32(newhdr+16,rawsz); p32(newhdr+20,rp)
    p32(newhdr+24,0);p32(newhdr+28,0);p16(newhdr+32,0);p16(newhdr+34,0);p32(newhdr+36,0xE0000060)
    p16(pe+6,n+1)
    p32(opt+56,align(va+len(code),sa))
    p32(opt+64,0)
    for name,info in wrappers.items():
        p32(exports[name]['eat_off'],info['wrapper_rva'])
    out.write_bytes(b)
    out_sha=hashlib.sha256(b).hexdigest()
    rep={'input':str(inp),'output':str(out),'input_sha256':in_sha,'output_sha256':out_sha,
         'image_base':hex(image_base),'section_rva':hex(va),'section_raw':hex(rp),'lock_rva':hex(va+lock_off),
         'wrappers':wrappers,'note':'Serializes all four exported ABI entrypoints with one in-module spinlock; original algorithm bodies unchanged.'}
    if report: report.write_text(json.dumps(rep,indent=2)+'\n')
    return rep

ap=argparse.ArgumentParser(); ap.add_argument('input'); ap.add_argument('output'); ap.add_argument('--report')
a=ap.parse_args(); r=patch(Path(a.input),Path(a.output),Path(a.report) if a.report else None); print(json.dumps(r,indent=2))
