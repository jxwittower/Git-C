#!/usr/bin/env python3
from pathlib import Path
import argparse, struct, hashlib, json

EXPECTED_INPUT_SHA = '1c2695f5f5d48228a9cfee18c31669cc27615d6d1c53bf83228aa015240a2b92'
SITES = [
    (0x1209, 0x2290),
    (0x2A04, 0x214C),
    (0x52F1, 0x8168),
    (0x79A9, 0x10F30),
    (0x1E7E9, 0x6F40),
    (0x21D79, 0xD6A0),
    (0x37141, 0x9DE0),
    (0x45FA9, 0x1070),
    (0x46549, 0x25A80),
    (0x4AB19, 0x4040),
    (0x4B749, 0x2048),
    (0x4DB16, 0x37E0),
]

def align(v, a):
    return (v + a - 1) // a * a

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--report')
    args = ap.parse_args()
    src = Path(args.input)
    out = Path(args.output)
    b = bytearray(src.read_bytes())
    in_sha = sha256(b)
    if in_sha != EXPECTED_INPUT_SHA:
        raise SystemExit(f'INPUT_SHA_MISMATCH {in_sha}')

    pe = struct.unpack_from('<I', b, 0x3c)[0]
    if b[pe:pe+4] != b'PE\0\0':
        raise SystemExit('NOT_PE')
    fh = pe + 4
    machine, ns = struct.unpack_from('<HH', b, fh)
    if machine != 0x14c:
        raise SystemExit(f'NOT_I386 machine=0x{machine:x}')
    opt_size = struct.unpack_from('<H', b, fh + 16)[0]
    opt = fh + 20
    magic = struct.unpack_from('<H', b, opt)[0]
    if magic != 0x10b:
        raise SystemExit(f'NOT_PE32 magic=0x{magic:x}')
    sec = opt + opt_size
    sec_align = struct.unpack_from('<I', b, opt + 32)[0]
    file_align = struct.unpack_from('<I', b, opt + 36)[0]

    sections=[]
    text=None
    for i in range(ns):
        o=sec+i*40
        name=bytes(b[o:o+8]).rstrip(b'\0').decode('ascii','replace')
        vs, va, rs, rp = struct.unpack_from('<IIII', b, o+8)
        sections.append((name,vs,va,rs,rp,o))
        if name=='.text':
            text=(vs,va,rs,rp,o)
    if text is None:
        raise SystemExit('NO_TEXT')
    if sec + (ns+1)*40 > min(x[4] for x in sections if x[4]):
        raise SystemExit('NO_SECTION_HEADER_SLACK')

    tvs,tva,trs,trp,_=text
    for rva, imm in SITES:
        fo=trp+(rva-tva)
        exp=b'\x81\xec'+struct.pack('<I',imm)
        if bytes(b[fo:fo+6]) != exp:
            raise SystemExit(f'PREPATCH_SITE_MISMATCH rva=0x{rva:x} got={bytes(b[fo:fo+6]).hex()} expected={exp.hex()}')

    helper_code=bytes.fromhex(
        '5152'
        '8b542408'
        '0fb602'
        '42'
        '89542408'
        'e800000000'
        '59'
        '8d893d000000'
        '8b0481'
        '8d54240c'
        '3d00100000'
        '7214'
        '81ea00100000'
        '8512'
        '2d00100000'
        '3d00100000'
        '77ec'
        '29c2'
        '8512'
        '8b4c2408'
        '894afc'
        '89d0'
        '5a59'
        '8d60fc'
        'c3'
        '9090'
    )
    table=b''.join(struct.pack('<I', imm) for _,imm in SITES)
    helper=helper_code+table
    if len(helper_code) != 0x51 or len(helper) != 0x51 + 4*len(SITES):
        raise SystemExit(f'HELPER_LAYOUT_ERROR code={len(helper_code)} total={len(helper)}')

    last=max(sections,key=lambda x:x[2])
    nva=align(last[2]+max(last[1],last[3]),sec_align)
    nrp=align(len(b),file_align)
    nrs=align(len(helper),file_align)
    if len(b)<nrp:
        b.extend(b'\0'*(nrp-len(b)))
    b.extend(helper)
    b.extend(b'\0'*(nrs-len(helper)))

    so=sec+ns*40
    b[so:so+8]=b'.stkfix\0'
    struct.pack_into('<IIIIIIHHI', b, so+8,
                     len(helper), nva, nrs, nrp, 0,0,0,0,0x60000020)
    struct.pack_into('<H', b, fh+2, ns+1)
    struct.pack_into('<I', b, opt+56, align(nva+len(helper),sec_align))
    struct.pack_into('<I', b, opt+4, struct.unpack_from('<I',b,opt+4)[0]+nrs)

    patches=[]
    for idx,(rva,imm) in enumerate(SITES):
        fo=trp+(rva-tva)
        exp=b'\x81\xec'+struct.pack('<I',imm)
        if bytes(b[fo:fo+6]) != exp:
            raise SystemExit(f'SITE_MISMATCH rva=0x{rva:x}')
        rel=(nva-rva-5)&0xffffffff
        repl=b'\xe8'+struct.pack('<I',rel)+bytes([idx])
        b[fo:fo+6]=repl
        patches.append({'index':idx,'rva':f'0x{rva:x}','frame':imm,
                        'file_offset':fo,'original':exp.hex(),'replacement':repl.hex()})

    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_bytes(b)
    out_sha=sha256(b)
    report={
        'input':str(src),'input_sha256':in_sha,'output':str(out),'output_sha256':out_sha,
        'machine':'i386','pe32':True,'original_sections':ns,'new_sections':ns+1,
        'stackfix_section_rva':f'0x{nva:x}','stackfix_section_raw':nrp,
        'helper_size':len(helper),'patched_site_count':len(patches),'patches':patches,
    }
    if args.report:
        Path(args.report).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()
