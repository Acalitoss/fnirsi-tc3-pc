import struct,unittest
from scripts.flash import frame,ack,firmware_frames

class UploadProtocolTests(unittest.TestCase):
    def test_bootloader_handshake(self):
        self.assertEqual(frame(0,1),bytes.fromhex('0001000001'))
        self.assertEqual(ack(0,1),bytes.fromhex('0101000002'))
    def test_counter_endianness_and_checksum(self):
        self.assertEqual(frame(0x10,256,b'\x12\x34'),bytes.fromhex('10000102123459'))
    def test_image_size_in_header_and_last_partial_frame(self):
        image=bytes(range(70));packets=list(firmware_frames(image))
        self.assertEqual(len(packets),3)
        self.assertEqual(struct.unpack_from('<I',packets[0],10)[0],70)
        self.assertEqual(packets[-1][3],6)
        self.assertEqual(packets[-1][4:-1],image[64:])
        for packet in packets:self.assertEqual(packet[-1],sum(packet[:-1])&255)
    def test_bad_frame_rejected(self):
        for counter,payload in [(-1,b''),(65536,b''),(0,bytes(33))]:
            with self.assertRaises(ValueError):frame(0x10,counter,payload)
