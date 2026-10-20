"""Experimental TC3 uploader, independently matched to all vendor frames.

Only transmits firmware after an exact bootloader-only handshake. Normal-mode
configuration replies are rejected before any write packet is sent.
"""
from pathlib import Path
import argparse,struct,time,json,hashlib,sys
root=Path.cwd()

def frame(command,counter,payload=b''):
    if not 0<=counter<=65535 or len(payload)>32:raise ValueError('Invalid frame')
    result=struct.pack('<BH',command,counter)+bytes([len(payload)])+payload
    return result+bytes([sum(result)&255])

def ack(command,counter):return frame((command+1)&255,counter)

def firmware_frames(data):
    data=bytearray(data)
    struct.pack_into('<I',data,6,len(data))
    for index,start in enumerate(range(0,len(data),32)):
        yield frame(0x10,index,bytes(data[start:start+32]))

def read_exact(port,size,timeout=3):
    output=bytearray();end=time.monotonic()+timeout
    while len(output)<size and time.monotonic()<end:
        output.extend(port.read(size-len(output)))
    return bytes(output)

def upload(path,port_name):
    import serial
    from serial.tools import list_ports
    data=path.read_bytes()
    expected_hashes={'9a97d5bb1a5864af6484b92f115ae827e16e3972f5ec8828362c358ba2430b61'}
    manifest_path=root/'build/manifest.json'
    if manifest_path.exists():expected_hashes.add(json.loads(manifest_path.read_text())['output_sha256'])
    digest=hashlib.sha256(data).hexdigest()
    if digest not in expected_hashes:raise ValueError('Image is not the verified original or current experiment')
    ports=list(list_ports.comports())
    matches=[p for p in ports if p.vid==0x19f5 and p.pid==0x5740]
    if port_name is None:
        if len(matches)!=1:raise ValueError(f'Expected one TC3, found {[(p.device,p.description) for p in ports]}')
        port_name=matches[0].device
    elif not any(p.device==port_name for p in matches):
        raise ValueError('Specified port does not match TC3 USB identity 19F5:5740')
    log_path=root/'captures'/('flash-'+time.strftime('%Y%m%d-%H%M%S')+'.jsonl')
    log_path.parent.mkdir(parents=True,exist_ok=True)
    started=False;done=False;sent=0
    with log_path.open('w',encoding='utf-8',buffering=1) as log:
        def record(**values):log.write(json.dumps(values)+'\n')
        record(event='start',image=str(path),sha256=digest,port=port_name,size=len(data))
        port=serial.Serial(port=None,baudrate=12000000,timeout=0.1,write_timeout=2)
        port.dtr=False;port.rts=False;port.port=port_name
        try:
            port.open();port.reset_input_buffer()
            request=frame(0,1)
            port.write(request)
            response=read_exact(port,5)
            record(event='handshake',request=request.hex(),response=response.hex())
            print('Handshake:',response.hex(),flush=True)
            if response!=ack(0,1):
                raise RuntimeError('Exact bootloader handshake not received; no firmware packet sent')
            started=True
            packets=list(firmware_frames(data));last_percent=-1
            for index,packet in enumerate(packets):
                port.write(packet)
                response=read_exact(port,5,5 if index==0 else 2)
                expected=ack(0x10,index)
                record(event='packet',counter=index,request_length=len(packet),response=response.hex(),ok=response==expected)
                if response!=expected:
                    raise RuntimeError(f'Packet {index}: expected {expected.hex()}, received {response.hex()}')
                sent=index+1
                percent=sent*100//len(packets)
                if percent!=last_percent and percent%5==0:
                    print(f'Upload {percent}% ({sent}/{len(packets)})',flush=True);last_percent=percent
            request=frame(0x20,len(packets))
            port.write(request);response=read_exact(port,5)
            record(event='run',request=request.hex(),response=response.hex())
            if response!=ack(0x20,len(packets)):raise RuntimeError('All packets acknowledged but restart acknowledgement not received')
            done=True
            print('All packets and restart acknowledged. Hardware behaviour still needs verification.',flush=True)
        except Exception as error:
            record(event='error',type=type(error).__name__,message=str(error),packets_acknowledged=sent)
            raise
        finally:
            if port.is_open:port.close()
            record(event='end',upload_started=started,upload_completed=done,packets_acknowledged=sent)
            print('Log:',log_path,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--image',type=Path,required=True)
    parser.add_argument('--port')
    args=parser.parse_args()
    upload(args.image,args.port)
