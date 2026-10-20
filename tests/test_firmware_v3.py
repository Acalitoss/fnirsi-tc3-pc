import os,unittest
from pathlib import Path
if not os.environ.get('TC3_STOCK_FIRMWARE'):raise unittest.SkipTest('Vendor image required')
from test_firmware import execute,root
from scripts.build_patch_v3 import build

class NavigationFirmwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):build(Path(os.environ['TC3_STOCK_FIRMWARE']),root/'build/v3')
    def run_packet(self,packet,mode=1):
        return execute(packet,version=2,image_path=root/'build/v3/application-decoded.bin',device_mode=mode)
    def test_protocol_signature(self):
        self.assertEqual(self.run_packet(bytes([0x21,0]))[0][:4],bytes.fromhex('a55a2103'))
    def test_navigation_modes(self):
        for mode in range(1,7):
            for key in (1,2,4,8,16,32,0x84):
                self.assertEqual(self.run_packet(bytes([0x30,key]),mode),[bytes.fromhex('a55a3000')])
    def test_no_power_or_calibration_long_keys(self):
        for key in (0,0x40,0x81,0x82,0xff):self.assertEqual(self.run_packet(bytes([0x30,key])),[])
    def test_disallowed_mode(self):
        for mode in (0,7,100,0xffffffff):self.assertEqual(self.run_packet(bytes([0x30,1]),mode),[])
    def test_bounded_state_pages(self):
        for page in range(32):
            packet=self.run_packet(bytes([0x22,page]))[0]
            self.assertEqual(packet[:4],bytes([0xa5,0x5a,page,56]))
            self.assertEqual(len(packet),60)
        for page in (32,255):self.assertEqual(self.run_packet(bytes([0x22,page])),[])
