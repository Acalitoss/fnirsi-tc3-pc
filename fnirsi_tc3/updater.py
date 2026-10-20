"""Bundled firmware installation. Never write before checking bootloader identity."""
from pathlib import Path
import hashlib,struct,sys,time
import serial
from serial.tools import list_ports

PATCH_SHA='97c601b5c02b2169e51275a6b5e7328f2919d3101c6a53bbdf8807274eb5c5ac'

def device_ports():
    return [p.device for p in list_ports.comports() if p.vid==0x19f5 and p.pid==0x5740]

def bundled_firmware():
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
    candidates=[root/'firmware/DSO-TC3-PC-v1.0-patched.s19',root/'build/DSO-TC3_V0.3_USB_EXPERIMENTAL.s19']
    for candidate in candidates:
        if candidate.is_file():return candidate
    raise FileNotFoundError('Firmware bulunamadı. GitHub v1.0 Release paketini kullanın.')

def packet(command,counter,payload=b''):
    result=struct.pack('<BH',command,counter)+bytes([len(payload)])+payload
    return result+bytes([sum(result)&255])

def install_firmware(progress):
    data=bundled_firmware().read_bytes()
    if hashlib.sha256(data).hexdigest()!=PATCH_SHA:raise ValueError('Firmware SHA-256 doğrulanamadı; yükleme iptal edildi.')
    ports=device_ports()
    if len(ports)!=1:raise RuntimeError('Tek bir DSO-TC3 USB aygıtı bağlı olmalı.')
    connection=serial.Serial(port=None,baudrate=12000000,timeout=0.1,write_timeout=2)
    connection.dtr=False;connection.rts=False;connection.port=ports[0]
    acknowledged=0
    try:
        connection.open();connection.reset_input_buffer()
        def exchange(command,counter,payload=b'',timeout=3):
            connection.write(packet(command,counter,payload))
            response=bytearray();deadline=time.monotonic()+timeout
            while len(response)<5 and time.monotonic()<deadline:
                response.extend(connection.read(5-len(response)))
            if bytes(response)!=packet(command+1,counter):
                raise RuntimeError(f'Cihaz onayı alınamadı (paket {counter}, yanıt {response.hex()}).')
        exchange(0,1)
        data=bytearray(data);struct.pack_into('<I',data,6,len(data))
        total=(len(data)+31)//32
        for index,start in enumerate(range(0,len(data),32)):
            exchange(0x10,index,bytes(data[start:start+32]),5 if index==0 else 2)
            acknowledged=index+1
            progress(acknowledged*100//total)
        exchange(0x20,total)
        return acknowledged
    except Exception as error:
        raise RuntimeError(f'{error} Onaylanan firmware paketi: {acknowledged}.') from error
    finally:
        if connection.is_open:connection.close()
