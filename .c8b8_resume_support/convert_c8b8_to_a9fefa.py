from pathlib import Path
import hashlib,sys
SOURCE_SHA='c8b8f49620b45707f80f47a9fadf14db376a115bc6052517e9243e0cb2dc20e9'
OUTPUT_SHA='a9fefa04b804c61d522d6e1ede59f078151400c1e5eec29d483e4a297049af34'
p=Path(sys.argv[1] if len(sys.argv)>1 else 'payload/SigProcDll-64HF.dll')
b=bytearray(p.read_bytes())
h=hashlib.sha256(b).hexdigest()
if h!=SOURCE_SHA: raise SystemExit(f'SOURCE_SHA_FAIL {h}')
patches=[
    (0x215, bytes.fromhex('3200')),
    (0x218, bytes.fromhex('ab01')),
    (0x1e05, bytes.fromhex('17')),
    (0x46f2, bytes.fromhex('4a')),
    (0x6daa, bytes.fromhex('b2')),
    (0x1d86a, bytes.fromhex('121c')),
    (0x20dfa, bytes.fromhex('a2')),
    (0x36242, bytes.fromhex('7a92')),
    (0x44dba, bytes.fromhex('22a7')),
    (0x4535a, bytes.fromhex('a2a1')),
    (0x49c3a, bytes.fromhex('e2')),
    (0x4a86a, bytes.fromhex('d24c')),
    (0x4cc37, bytes.fromhex('2529')),
    (0x6ba00, bytes.fromhex('50518d4c2404b88422')),
    (0x6ba0a, bytes.fromhex('00e87001')),
    (0x6ba0f, bytes.fromhex('008b01ff71048b49fcc39090909090909050518d4c2404b840210000e8500100')),
    (0x6ba30, bytes.fromhex('8b01ff71048b49fcc39090909090909050518d4c2404')),
    (0x6ba47, bytes.fromhex('5c81')),
    (0x6ba4b, bytes.fromhex('e83001')),
    (0x6ba50, bytes.fromhex('8b01ff71048b49fcc39090909090909050518d4c2404b8f40e0100e8100100008b01ff71048b49fcc39090909090909050518d4c2404b8346f0000e8f00000008b01ff71048b49fcc39090909090909050518d4c2404b884d6')),
    (0x6baab, bytes.fromhex('e8d0')),
    (0x6bab0, bytes.fromhex('8b01ff71048b49fcc39090909090909050518d4c2404b8b49d')),
    (0x6bacb, bytes.fromhex('e8b0')),
    (0x6bad0, bytes.fromhex('8b01ff71048b49fcc39090909090909050518d4c2404b86410')),
    (0x6baeb, bytes.fromhex('e890')),
    (0x6baf0, bytes.fromhex('8b01ff71048b49fcc39090909090909050518d4c2404b8745a02')),
    (0x6bb0b, bytes.fromhex('e870')),
    (0x6bb10, bytes.fromhex('8b01ff71048b49fcc39090909090909050518d4c2404b83440')),
    (0x6bb2b, bytes.fromhex('e850')),
    (0x6bb30, bytes.fromhex('8b01ff71048b49fcc39090909090909050518d4c2404b83c20')),
    (0x6bb4b, bytes.fromhex('e830')),
    (0x6bb50, bytes.fromhex('8b01ff71048b49fcc39090909090909050518d4c2404b8d437')),
    (0x6bb6b, bytes.fromhex('e810')),
    (0x6bb70, bytes.fromhex('8b01ff71048b240429c119c0f7d021c189e025')),
    (0x6bb91, bytes.fromhex('f0ffff39c1720a89c859948b')),
    (0x6bb9e, bytes.fromhex('890424c32d')),
    (0x6bba4, bytes.fromhex('10')),
    (0x6bba7, bytes.fromhex('85')),
    (0x6bba9, bytes.fromhex('ebe9')),
]
for off,data in patches: b[off:off+len(data)]=data
h=hashlib.sha256(b).hexdigest()
if h!=OUTPUT_SHA: raise SystemExit(f'OUTPUT_SHA_FAIL {h}')
p.write_bytes(b)
print(f'C8B8_TO_A9FEFA_PATCH_PASS SHA256={h} PATCH_RANGES={len(patches)}')
