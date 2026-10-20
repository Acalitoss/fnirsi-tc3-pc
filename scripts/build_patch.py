"""Apply the reviewed USB handler to one exact vendor V0.3 file."""
from pathlib import Path
import argparse,hashlib,json

SOURCE_SHA='9a97d5bb1a5864af6484b92f115ae827e16e3972f5ec8828362c358ba2430b61'
BASE=0x08004000
HANDLER=0x08013f08
END=0x08014094
EXPECTED_OUTPUT='97c601b5c02b2169e51275a6b5e7328f2919d3101c6a53bbdf8807274eb5c5ac'

def build(firmware,output):
    from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
    from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
    original=Path(firmware).read_bytes()
    if hashlib.sha256(original).hexdigest()!=SOURCE_SHA:
        raise ValueError('Unsupported original firmware SHA-256; only the documented V0.3 file is accepted')
    decoded=bytearray(value^127 for value in original)
    start=HANDLER-BASE+64;length=END-HANDLER
    if decoded[start:start+4]!=bytes.fromhex('70b50446'):raise ValueError('USB handler signature mismatch')
    path=Path(__file__).resolve().parents[1]/'firmware/usb_handler.s'
    assembly='\n'.join(line.split('//')[0] for line in path.read_text(encoding='utf-8').splitlines())
    encoded,_=Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(assembly,HANDLER)
    patch=bytes(encoded)
    if len(patch)>length or len(patch)%2:raise ValueError('Handler does not fit the reserved region')
    instructions=list(Cs(CS_ARCH_ARM,CS_MODE_THUMB).disasm(patch,HANDLER))
    if not any(i.mnemonic=='b.w' and i.op_str=='#0x8005158' for i in instructions):
        raise ValueError('USB transmit branch was not assembled correctly')
    patched=bytearray(decoded)
    patched[start:start+length]=patch+bytes.fromhex('00bf')*((length-len(patch))//2)
    result=bytes(value^127 for value in patched)
    if len(result)!=len(original) or result[:start]!=original[:start] or result[start+length:]!=original[start+length:]:
        raise ValueError('Bytes outside the replacement region changed')
    digest=hashlib.sha256(result).hexdigest()
    if digest!=EXPECTED_OUTPUT:raise ValueError('Output differs from the hardware-tested image')
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/'DSO-TC3_V0.3_USB_EXPERIMENTAL.s19').write_bytes(result)
    (output/'application-decoded.bin').write_bytes(patched[64:])
    (output/'original-decoded.bin').write_bytes(decoded)
    (output/'usb-handler.bin').write_bytes(patch)
    manifest={'source_sha256':SOURCE_SHA,'output_sha256':digest,'protocol':2,'revision':2,
              'patch_address':hex(HANDLER),'patch_file_offset':hex(start),'patch_bytes':length,
              'handler_bytes':len(patch),'outer_validation':'original header preserved; not fully decoded',
              'hardware_status':'tested on one DSO-TC3 V0.3 and Windows PC'}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('build'))
    args=parser.parse_args()
    print(json.dumps(build(args.firmware,args.output),indent=2))
