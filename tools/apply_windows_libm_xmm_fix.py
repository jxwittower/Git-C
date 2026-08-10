#!/usr/bin/env python3
from pathlib import Path
import argparse, struct, hashlib, json

EXPECTED_INPUT_SHA = 'ca82d1c611eb02afa5e3a42c5baeefb5983efee3d36b1ebf99b61e1b334179e9'
# Existing C ABI wrapper RVAs in the frozen RC3 link. Each currently occupies
# a 16-byte slot and tail-jumps directly to a UCRT private SSE2 thunk, which is
# wrong for ordinary x86 cdecl callers because those callers pass doubles on
# the stack and expect a double result in x87 ST0.
WRAPPERS = [
    ('acos',  0x64680, 0x64856, 1),
    ('asin',  0x64690, 0x6485C, 1),
    ('cos',   0x646A0, 0x64862, 1),
    ('exp',   0x646B0, 0x64868, 1),
    ('log10', 0x646C0, 0x6486E, 1),
    ('log',   0x646D0, 0x64874, 1),
    ('pow',   0x646E0, 0x6487A, 2),
    ('sin',   0x646F0, 0x64880, 1),
    ('sqrt',  0x64700, 0x64886, 1),
]

def align(v, a):
    return (v + a - 1) // a * a

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def rel32(src_next_rva, dst_rva):
    return (dst_rva - src_next_rva) & 0xffffffff

def unary_stub(stub_rva, thunk_rva):
    code = bytearray(b'\xF2\x0F\x10\x44\x24\x04')
    call_rva = stub_rva + len(code)
    code += b'\xE8' + struct.pack('<I', rel32(call_rva + 5, thunk_rva))
    code += b'\xF2\x0F\x11\x44\x24\x04'
    code += b'\xDD\x44\x24\x04'
    code += b'\xC3'
    return bytes(code)

def binary_stub(stub_rva, thunk_rva):
    code = bytearray(b'\xF2\x0F\x10\x44\x24\x04')
    code += b'\xF2\x0F\x10\x4C\x24\x0C'
    call_rva = stub_rva + len(code)
    code += b'\xE8' + struct.pack('<I', rel32(call_rva + 5, thunk_rva))
    code += b'\xF2\x0F\x11\x44\x24\x04'
    code += b'\xDD\x44\x24\x04'
    code += b'\xC3'
    return bytes(code)

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
    if struct.unpack_from('<H', b, opt)[0] != 0x10b:
        raise SystemExit('NOT_PE32')
    sec = opt + opt_size
    sec_align = struct.unpack_from('<I', b, opt + 32)[0]
    file_align = struct.unpack_from('<I', b, opt + 36)[0]

    sections=[]
    text=None
    for i in range(ns):
        o = sec + i*40
        name = bytes(b[o:o+8]).rstrip(b'\0').decode('ascii','replace')
        vs, va, rs, rp = struct.unpack_from('<IIII', b, o+8)
        sections.append((name,vs,va,rs,rp,o))
        if name == '.text': text = (vs,va,rs,rp,o)
    if text is None: raise SystemExit('NO_TEXT')
    first_raw = min(x[4] for x in sections if x[4])
    if sec + (ns+1)*40 > first_raw:
        raise SystemExit('NO_SECTION_HEADER_SLACK')

    tvs,tva,trs,trp,_ = text
    bindings=[]
    for name,rva,thunk,arity in WRAPPERS:
        fo = trp + (rva-tva)
        expected = b'\xE9' + struct.pack('<I', rel32(rva+5, thunk))
        got = bytes(b[fo:fo+5])
        if got != expected:
            raise SystemExit(f'WRAPPER_PREPATCH_MISMATCH {name} rva=0x{rva:x} got={got.hex()} expected={expected.hex()}')
        bindings.append((name,rva,thunk,arity,fo,expected))

    last = max(sections, key=lambda x:x[2])
    nva = align(last[2] + max(last[1],last[3]), sec_align)
    nrp = align(len(b), file_align)

    slot_size = 0x20
    payload = bytearray()
    stub_meta=[]
    for idx,(name,rva,thunk,arity,fo,expected) in enumerate(bindings):
        stub_rva = nva + idx*slot_size
        stub = unary_stub(stub_rva, thunk) if arity == 1 else binary_stub(stub_rva, thunk)
        if len(stub) > slot_size:
            raise SystemExit(f'STUB_TOO_LARGE {name} {len(stub)}')
        payload += stub + b'\x90'*(slot_size-len(stub))
        stub_meta.append((name,rva,thunk,arity,fo,expected,stub_rva,stub))

    nrs = align(len(payload), file_align)
    if len(b) < nrp: b.extend(b'\0'*(nrp-len(b)))
    b.extend(payload)
    b.extend(b'\0'*(nrs-len(payload)))

    so = sec + ns*40
    b[so:so+8] = b'.mathfix'
    struct.pack_into('<IIIIIIHHI', b, so+8,
                     len(payload), nva, nrs, nrp, 0,0,0,0,0x60000020)
    struct.pack_into('<H', b, fh+2, ns+1)
    struct.pack_into('<I', b, opt+56, align(nva+len(payload), sec_align))
    struct.pack_into('<I', b, opt+4, struct.unpack_from('<I',b,opt+4)[0]+nrs)

    patches=[]
    for name,rva,thunk,arity,fo,expected,stub_rva,stub in stub_meta:
        repl = b'\xE9' + struct.pack('<I', rel32(rva+5, stub_rva))
        if bytes(b[fo:fo+5]) != expected:
            raise SystemExit(f'WRAPPER_CHANGED_DURING_PATCH {name}')
        b[fo:fo+5] = repl
        patches.append({
            'name':name,'arity':arity,'wrapper_rva':f'0x{rva:x}',
            'ucrt_thunk_rva':f'0x{thunk:x}','bridge_rva':f'0x{stub_rva:x}',
            'original':expected.hex(),'replacement':repl.hex(),
            'bridge_bytes':stub.hex(),
        })

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b)
    out_sha = sha256(b)
    report={
        'input':str(src),'input_sha256':in_sha,'output':str(out),'output_sha256':out_sha,
        'machine':'i386','pe32':True,'original_sections':ns,'new_sections':ns+1,
        'mathfix_section_rva':f'0x{nva:x}','mathfix_section_raw':nrp,
        'mathfix_virtual_size':len(payload),'mathfix_raw_size':nrs,
        'patched_wrapper_count':len(patches),'patches':patches,
    }
    if args.report:
        Path(args.report).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__ == '__main__':
    main()
