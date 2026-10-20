from pathlib import Path
import tempfile,unittest,importlib.util
from scripts.build_patch import build

@unittest.skipUnless(importlib.util.find_spec('keystone') and importlib.util.find_spec('capstone'),'Install firmware extras to test the patch guard')
class PatchGuardTests(unittest.TestCase):
    def test_rejects_unknown_firmware_before_writing_output(self):
        temporary_root=Path(__file__).resolve().parents[1]/'build'
        temporary_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root) as folder:
            source=Path(folder)/'unknown.s19';source.write_bytes(b'not a supported firmware')
            output=Path(folder)/'output'
            with self.assertRaisesRegex(ValueError,'SHA-256'):build(source,output)
            self.assertFalse(output.exists())
