"""DSO-TC3 USB reader for the experimental V0.3 sample-transfer firmware.

Reads 600 signed memory samples. Physical units and atomic snapshots are not
yet validated. Stock V0.3 supports only the configuration read implemented here.
"""
from dataclasses import dataclass
import argparse
import json
import struct
import time
from pathlib import Path
import sys

SCALE_MV=(10,20,50,100,200,500,1000,2000,5000,10000)
SCALE_LABELS=('10mV','20mV','50mV','100mV','200mV','500mV','1V','2V','5V','10V')
TIME_LABELS=('1us','2us','5us','10us','20us','50us','100us','200us','500us','1ms','2ms','5ms','10ms','20ms','50ms','100ms','200ms','500ms','1s','2s','5s','10s')

def parse_state(data):
    if len(data) not in (224,1792):raise ValueError('State snapshot must contain 224 bytes')
    integer=lambda offset:struct.unpack_from('<I',data,offset)[0]
    result={name:integer(offset) for name,offset in {'device_mode':0x20,'scale_index':0x28,'probe_index':0x2c,'timebase_index':0x30,'coupling_index':0x34,'trigger_mode':0x3c,'trigger_edge':0x40,'trigger_sample':0xa8}.items()}
    result['offset_raw']=struct.unpack_from('<i',data,0x24)[0]
    result['device_hold']=bool(data[0xa1])
    result['key_pending']=data[0x90]
    fields=('vmax','vmin','vpp','vrms','vavg','frequency_khz','duty_percent','cycle_ms')
    result['measurements']=dict(zip(fields,struct.unpack_from('<8f',data,0xb4)))
    return result


@dataclass(frozen=True)
class Configuration:
    raw_values: tuple[int, int, int, int]

    @classmethod
    def from_packet(cls, packet: bytes):
        if len(packet) != 18:
            raise ValueError(f'Expected 18 bytes, received {len(packet)}')
        if packet[:2] != b'\x01\xfe':
            raise ValueError(f'Unexpected response header: {packet[:2].hex()}')
        return cls(struct.unpack('>4I', packet[2:]))


class TC3:
    def __init__(self, port='COM7', baudrate=12000000):
        import serial
        self.serial = serial.Serial(port=None, baudrate=baudrate, timeout=0.1,
                                    write_timeout=1)
        self.serial.dtr = False
        self.serial.rts = False
        self.serial.port = port

    def __enter__(self):
        self.serial.open()
        return self

    def __exit__(self, *_):
        self.serial.close()

    def read_configuration(self, timeout=3):
        # Exact vendor beat packet, verified against the normal-mode device.
        # In normal mode its first byte selects configuration read.
        self.serial.reset_input_buffer()
        self.serial.write(b'\x00\x01\x00\x00\x01')
        packet = bytearray()
        deadline = time.monotonic() + timeout
        while len(packet) < 18 and time.monotonic() < deadline:
            packet.extend(self.serial.read(18-len(packet)))
        return Configuration.from_packet(bytes(packet))

    def read_waveform(self):
        metadata=self.read_metadata()
        if metadata.get('device_mode',3)!=3:return metadata,[]
        samples=[]
        for page in range(21):
            count=29 if page<20 else 20
            packet=self._request(bytes([0x20,page]),4+count*2)
            if packet[:4]!=bytes([0xa5,0x5a,page,count]):
                raise ValueError(f'Invalid sample page {page}: {packet.hex()}')
            samples.extend(struct.unpack('<'+'h'*count,packet[4:]))
        return metadata,samples

    def _request(self,request,size,timeout=2):
        self.serial.reset_input_buffer()
        self.serial.write(request)
        result=bytearray();deadline=time.monotonic()+timeout
        while len(result)<size and time.monotonic()<deadline:
            result.extend(self.serial.read(size-len(result)))
        if len(result)!=size:raise TimeoutError(f'Request {request.hex()}: expected {size}, received {len(result)} bytes ({result.hex()})')
        return bytes(result)

    def read_metadata(self):
        packet=self._request(b'\x21\x00',24)
        if packet[:3]!=b'\xa5\x5a\x21' or packet[3] not in (1,2,3):
            raise ValueError(f'Experimental firmware signature absent: {packet.hex()}')
        offset,scale,timebase,rate,count=struct.unpack('<iIIfI',packet[4:])
        metadata={'offset_raw':offset,'scale_index':scale,'timebase_index':timebase,
                'sample_rate_raw':rate,'sample_count':count,'protocol_version':1}
        self.protocol_version=packet[3]
        if packet[3]>=2:
            metadata.update(protocol_version=packet[3],focus=count,sample_count=600)
            metadata.update(self.read_state())
        return metadata

    def read_state(self):
        result=bytearray()
        for page in range(32 if getattr(self,'protocol_version',2)>=3 else 4):
            packet=self._request(bytes([0x22,page]),60)
            if packet[:4]!=bytes([0xa5,0x5a,page,56]):raise ValueError('Invalid state page')
            result.extend(packet[4:])
        state=parse_state(bytes(result))
        if len(result)>224:
            from .instrument import parse_instrument_state
            state.update(parse_instrument_state(bytes(result)))
        return state

    def press_key(self,key):
        if key not in ((1,2,4,8,16,32,0x84) if getattr(self,'protocol_version',2)>=3 else (2,4,8,16,32,0x84)):raise ValueError('Unsupported remote key')
        for attempt in range(8):
            response=self._request(bytes([0x30,key]),4)
            if response[:3]!=b'\xa5\x5a\x30':raise ValueError('Invalid remote key response')
            if response[3]==0:
                deadline=time.monotonic()+4
                while time.monotonic()<deadline:
                    time.sleep(0.05)
                    if self.read_state()['key_pending']==0:
                        time.sleep(0.12)
                        return
                raise RuntimeError('Device acknowledged key but did not finish processing it')
            if response[3]!=1:raise RuntimeError('Remote key rejected')
            time.sleep(0.08)
        raise RuntimeError('Device key handler remained busy')

    def select_mode(self,name):
        from .instrument import MODES
        if name not in MODES:raise ValueError('Unknown mode')
        state=self.read_metadata()
        if state['protocol_version']<3:raise RuntimeError('Multi-mode control requires firmware v3')
        target=MODES[name]
        if state['device_mode']==target:return state
        if state['device_mode']!=1:
            self.press_key(1);state=self.read_metadata()
        if state['device_mode']!=1:raise RuntimeError('Device did not return to home screen')
        if target==1:return state
        index={'tester':0,'oscilloscope':1,'generator':2,'tools':3}[name]
        for _ in range(4):
            if state.get('home_selection')==index:break
            self.press_key(16);state=self.read_metadata()
        if state.get('home_selection')!=index:raise RuntimeError('Home selection readback failed')
        self.press_key(2);state=self.read_metadata()
        if state['device_mode']!=target:raise RuntimeError('Mode change readback failed')
        return state
    def select_item(self,index):
        state=self.read_metadata()
        if state['protocol_version']<3:raise RuntimeError('Multi-mode control requires firmware v3')
        if state['device_mode'] not in (4,5):raise RuntimeError('Open Generator or Tools first')
        if not 0<=index<=5:raise ValueError('Item out of range')
        if state['device_mode']==4:
            self.press_key(4);self.press_key(4);state=self.read_metadata()
        for _ in range(12):
            current=state['instrument_selection']
            if current==index:return state
            self.press_key(8 if current<index else 32);state=self.read_metadata()
        raise RuntimeError('Selection was not applied; exit the digit editor with LEFT and retry')
    def set_control(self,name,value):
        controls={'scale_index':(2,9),'probe_index':(3,1),'timebase_index':(4,21),'coupling_index':(5,1),'trigger_edge':(7,1),'trigger_mode':(8,2)}
        state=self.read_metadata()
        if state['protocol_version']<2:raise RuntimeError('PC control requires firmware v2')
        if state['device_mode']!=3:raise RuntimeError('Device must be on the oscilloscope screen')
        if name=='device_hold':
            if state['device_hold']!=bool(value):self.press_key(0x84)
        elif name=='auto':self.press_key(2)
        elif name in controls:
            focus,maximum=controls[name]
            if not 0<=value<=maximum:raise ValueError('Setting out of range')
            for _ in range(9):
                if state['focus']==focus:break
                self.press_key(16);state=self.read_metadata()
            if state['focus']!=focus:raise RuntimeError('Device did not select requested control')
            for _ in range(maximum+2):
                if state[name]==value:break
                self.press_key(32 if state[name]<value or name in ('coupling_index','trigger_edge') else 8)
                state=self.read_metadata()
            if state[name]!=value:raise RuntimeError('Device did not apply requested value')
        else:raise ValueError('Unknown device control')
        result=self.read_metadata()
        if name=='device_hold' and result['device_hold']!=bool(value):raise RuntimeError('Device RUN/HOLD readback failed')
        return result


def main():
    parser = argparse.ArgumentParser(description='FNIRSI DSO-TC3 verified USB reader')
    parser.add_argument('--port', default='COM7')
    parser.add_argument('--baud', type=int, default=12000000)
    parser.add_argument('--waveform',action='store_true')
    args = parser.parse_args()
    try:
        with TC3(args.port, args.baud) as device:
            if args.waveform:
                metadata,samples=device.read_waveform()
                result={'port':args.port,'metadata':metadata,'samples_raw':samples}
                target=Path.cwd()/'captures'/('waveform-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(json.dumps(result,indent=2),encoding='utf-8')
                print(json.dumps({'saved':str(target),'metadata':metadata,'min_raw':min(samples),'max_raw':max(samples),'first_samples':samples[:20]},indent=2))
            else:
                config = device.read_configuration()
                print(json.dumps({'port': args.port, 'configuration_raw': config.raw_values}, indent=2))
    except Exception as error:
        parser.exit(1, f'{type(error).__name__}: {error}\n')


if __name__ == "__main__":
    main()
