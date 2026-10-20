import unittest
from fnirsi_tc3.driver import Configuration, TC3,parse_state
import struct


class ProtocolTests(unittest.TestCase):
    def test_real_capture(self):
        packet = bytes.fromhex('01fe000013880000141000004e2000004f27')
        self.assertEqual(Configuration.from_packet(packet).raw_values,
                         (5000, 5136, 20000, 20263))

    def test_reject_truncated_packet(self):
        with self.assertRaises(ValueError):
            Configuration.from_packet(b'\x01\xfe\x00')

    def test_reject_unexpected_header(self):
        with self.assertRaises(ValueError):
            Configuration.from_packet(bytes(18))

    def test_signed_waveform_words(self):
        device=TC3.__new__(TC3)
        device.read_metadata=lambda:{'sample_count':600}
        expected=[-1,0,-32768,32767]*150
        def request(packet,size):
            page=packet[1];count=29 if page<20 else 20
            values=expected[page*29:page*29+count]
            return bytes([0xa5,0x5a,page,count])+struct.pack('<'+'h'*count,*values)
        device._request=request
        metadata,samples=device.read_waveform()
        self.assertEqual(samples,expected)
    def test_device_measurements_and_settings(self):
        state=bytearray(224)
        struct.pack_into('<I',state,0x20,3)
        struct.pack_into('<3I',state,0x28,6,0,12)
        struct.pack_into('<8f',state,0xb4,5.03,4.94,0.09,4.98,4.98,0,0,0)
        result=parse_state(state)
        self.assertAlmostEqual(result['measurements']['vavg'],4.98,places=5)
        self.assertAlmostEqual(result['measurements']['vmax'],5.03,places=5)
        self.assertEqual(result['scale_index'],6)
        self.assertEqual(result['timebase_index'],12)


if __name__ == '__main__':
    unittest.main()
