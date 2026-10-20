"""Bounded instrument state decoded from the original V0.3 UI routines."""
import struct,math
MODES={'home':1,'tester':2,'oscilloscope':3,'generator':4,'tools':5,'settings':6}
WAVEFORMS=('Sine','Square','Pulse','Triangle','Ramp','DC')
TOOLS=('ON-OFF','Voltage','DS18B20','DHT11','IR Decode','Calibrate')
TESTER_TYPES=('Unknown','Testing','J-FET','Dmos','Transistor','Darlington','UJT','MOSFET','Thyristor','Triac','Diode','2-Diode','Cell','Capacitor','Resistor','Inductor','Zener','IR Decoder','DS18B20','DHT11')
MODE_NAMES={1:'Ana menü',2:'M-Tester',3:'Osiloskop',4:'Generator',5:'Tools',6:'Ayarlar'}

def parse_instrument_state(data):
    if len(data)!=1792:raise ValueError('Extended state must contain 1792 bytes')
    integer=lambda offset:struct.unpack_from('<I',data,offset)[0]
    def number(offset):
        value=struct.unpack_from('<f',data,offset)[0]
        return value if math.isfinite(value) else None
    return {'home_selection':integer(0x1c),'instrument_selection':integer(0x94),
            'generator':{'frequency_hz':integer(0x48),'duty_percent':integer(0x4c),'amplitude_v':number(0x50)},
            'tools':{'voltage_v':number(0xd8),'sensor_temperature':number(0x13c),'sensor_humidity':number(0x140),'ir_received':bool(data[0x150]),'ir_code':integer(0x154)},
            'tester':{'type_code':integer(0xe0),'pins':[integer(x)+1 for x in (0xe8,0xec,0xf0)],'primary_value':number(0x108),'capacitance_pf':number(0x104),'esr_ohm':number(0x108),'inductance_uh':number(0x10c),'voltage_v':number(0xfc),'gain':number(0x104),'vbe_v':number(0x114),'collector_ma':number(0x118),'leakage_ma':number(0x120),'cell_voltage_v':number(0x118),'diode_leakage_a':number(0x110),'loss_percent':number(0x100),'type_name':TESTER_TYPES[integer(0xe0)] if integer(0xe0)<len(TESTER_TYPES) else 'Unknown'},
            'state_hex':data.hex()}
