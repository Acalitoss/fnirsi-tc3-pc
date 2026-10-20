from pathlib import Path
import sys,struct,unittest
root=Path(__file__).resolve().parents[1]
import os
if not os.environ.get('TC3_STOCK_FIRMWARE'):raise unittest.SkipTest('Set TC3_STOCK_FIRMWARE to run vendor-dependent ARM tests')
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *

HANDLER=0x08013f08; TX=0x08005158; RETURN=0x0803f000
BUFFER=0x2000b69c; STACK=0x20018e00; SYS=0x20000668; SAMPLES=SYS+0x594
KNOWN=struct.pack('>4I',5000,5136,20000,20263)

def execute(request,original=False,version=1,key_status=0,return_state=False):
    uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
    uc.mem_map(0x08000000,0x100000)
    uc.mem_map(0x20000000,0x20000)
    if original:
        image=(root/'build/original-decoded.bin').read_bytes()[64:]
    else:
        image=(root/'build/application-decoded.bin').read_bytes()
    uc.mem_write(0x08004000,image)
    uc.mem_write(SYS+0x7c,struct.pack('<4I',5000,5136,20000,20263))
    uc.mem_write(SYS+0x24,struct.pack('<4I',123,4,0,7))
    uc.mem_write(SYS+0xb0,struct.pack('<f',10000000.0))
    uc.mem_write(SYS+0x20,struct.pack('<I',3))
    uc.mem_write(SYS+0x90,bytes([key_status,0]))
    uc.mem_write(0x20000144,struct.pack('<I',2))
    uc.mem_write(0x20000140,b'\x01')
    samples=struct.pack('<600H',*range(600))
    uc.mem_write(SAMPLES,samples)
    uc.mem_write(BUFFER,request)
    uc.reg_write(UC_ARM_REG_R0,BUFFER)
    uc.reg_write(UC_ARM_REG_R1,len(request))
    uc.reg_write(UC_ARM_REG_SP,STACK)
    uc.reg_write(UC_ARM_REG_LR,RETURN|1)
    initial={UC_ARM_REG_R4:0x4444,UC_ARM_REG_R5:0x5555,UC_ARM_REG_R6:0x6666}
    for register,value in initial.items():uc.reg_write(register,value)
    transmitted=[];unexpected=[]
    def code_hook(emu,address,size,_):
        if address==TX:
            pointer=emu.reg_read(UC_ARM_REG_R0);length=emu.reg_read(UC_ARM_REG_R1)
            if not 0<length<64:raise AssertionError('USB helper rejects length >=64')
            transmitted.append(bytes(emu.mem_read(pointer,length)))
            emu.emu_stop()
        elif address==RETURN:emu.emu_stop()
        elif original and address==0x080147c4:
            # Ignore printf calls used by original code; emulate a return.
            emu.reg_write(UC_ARM_REG_PC,emu.reg_read(UC_ARM_REG_LR))
    def write_hook(emu,access,address,size,value,_):
        if not (BUFFER<=address and address+size<=BUFFER+64 or STACK-64<=address and address+size<=STACK or version==2 and SYS+0x90<=address and address+size<=SYS+0x92 or version==2 and address==0x20000140 and size==1):
            unexpected.append((hex(address),size))
    uc.hook_add(UC_HOOK_CODE,code_hook)
    uc.hook_add(UC_HOOK_MEM_WRITE,write_hook)
    uc.emu_start(HANDLER|1,RETURN+2,count=10000)
    assert not unexpected,unexpected
    assert uc.reg_read(UC_ARM_REG_SP)==STACK
    for register,value in initial.items():assert uc.reg_read(register)==value
    assert bytes(uc.mem_read(SAMPLES,1200))==samples
    if return_state:return transmitted,bytes(uc.mem_read(SYS,224))
    return transmitted

class V2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from scripts.build_patch import build
        build(Path(os.environ['TC3_STOCK_FIRMWARE']),root/'build')
    def test_repeated_run_hold_with_original_device_key_handler(self):
        uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        uc.mem_map(0x08000000,0x100000);uc.mem_map(0x20000000,0x20000)
        uc.mem_write(0x08004000,(root/'build/application-decoded.bin').read_bytes())
        uc.mem_write(SYS+0x20,struct.pack('<I',3))
        uc.mem_write(0x20000140,b'\x01')
        ignored={0x08004e70,0x08011d20,0x08025b6c,0x08026028}
        def hook(emu,address,size,_):
            if address in (TX,RETURN):emu.emu_stop()
            elif address in ignored:emu.reg_write(UC_ARM_REG_PC,emu.reg_read(UC_ARM_REG_LR))
        uc.hook_add(UC_HOOK_CODE,hook)
        for expected in (1,0,1,0):
            uc.mem_write(BUFFER,b'\x30\x84')
            uc.reg_write(UC_ARM_REG_R0,BUFFER);uc.reg_write(UC_ARM_REG_R1,2)
            uc.reg_write(UC_ARM_REG_SP,STACK);uc.reg_write(UC_ARM_REG_LR,RETURN|1)
            uc.emu_start(HANDLER|1,RETURN+2,count=10000)
            self.assertEqual(bytes(uc.mem_read(0x20000140,1)),b'\x00')
            uc.reg_write(UC_ARM_REG_SP,STACK);uc.reg_write(UC_ARM_REG_LR,RETURN|1)
            uc.emu_start(0x08007f9d,RETURN+2,count=10000)
            self.assertEqual(bytes(uc.mem_read(SYS+0xa1,1)),bytes([expected]))
            self.assertEqual(bytes(uc.mem_read(SYS+0x90,1)),b'\x00')
    def test_configuration_compatibility(self):
        self.assertEqual(execute(b'\x00\x00',version=2),[b'\x01\xfe'+KNOWN])
    def test_metadata_version_and_focus(self):
        packet=execute(b'\x21\x00',version=2)[0]
        self.assertEqual(packet[:4],b'\xa5\x5a\x21\x02')
        self.assertEqual(struct.unpack_from('<I',packet,20)[0],2)
    def test_state_pages(self):
        data=b''
        for page in range(4):
            packet,state=execute(bytes([0x22,page]),version=2,return_state=True)
            self.assertEqual(packet[0][:4],bytes([0xa5,0x5a,page,56]))
            data+=packet[0][4:]
        self.assertEqual(data,state)
    def test_remote_keys(self):
        for key in (2,4,8,16,32):
            packets,state=execute(bytes([0x30,key]),version=2,return_state=True)
            self.assertEqual(packets,[b'\xa5\x5a\x30\x00'])
            self.assertEqual(state[0x90:0x92],bytes([1,key]))
    def test_busy_key_not_overwritten(self):
        packets,state=execute(b'\x30\x08',version=2,key_status=1,return_state=True)
        self.assertEqual(packets,[b'\xa5\x5a\x30\x01'])
        self.assertEqual(state[0x90:0x92],b'\x01\x00')
    def test_long_left_run_hold(self):
        packets,state=execute(b'\x30\x84',version=2,return_state=True)
        self.assertEqual(packets,[b'\xa5\x5a\x30\x00'])
        self.assertEqual(state[0x90:0x92],b'\xfe\x04')
    def test_bad_state_pages_and_keys_ignored(self):
        for packet in (b'\x22\x04',b'\x22\xff',b'\x30\x01',b'\x30\x00',b'\x30\xff'):
            self.assertEqual(execute(packet,version=2),[])
    def test_samples_unchanged(self):
        data=b''.join(execute(bytes([0x20,page]),version=2)[0][4:] for page in range(21))
        self.assertEqual(data,struct.pack('<600H',*range(600)))

if __name__=='__main__':unittest.main()
