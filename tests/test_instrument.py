import unittest,struct
from fnirsi_tc3.instrument import parse_instrument_state
from fnirsi_tc3.driver import TC3
from unittest.mock import Mock

class InstrumentTests(unittest.TestCase):
 def test_state_fields_do_not_alias_scope(self):
  b=bytearray(1792)
  for o,v in [(0x1c,2),(0x94,4),(0x48,1234),(0x4c,37),(0xe0,14)]:struct.pack_into('<I',b,o,v)
  for o,v in [(0x50,2.5),(0xd8,5.0),(0x108,1000.0)]:struct.pack_into('<f',b,o,v)
  s=parse_instrument_state(b)
  self.assertEqual(s['generator'],{'frequency_hz':1234,'duty_percent':37,'amplitude_v':2.5})
  self.assertEqual(s['tools']['voltage_v'],5.)
  self.assertEqual(s['tester']['type_name'],'Resistor')
  self.assertEqual(s['tester']['primary_value'],1000.)
 def test_nonfinite_is_absent(self):
  b=bytearray(1792);struct.pack_into('<f',b,0x50,float('nan'))
  self.assertIsNone(parse_instrument_state(b)['generator']['amplitude_v'])
 def test_no_old_waveform_in_other_modes(self):
  d=TC3.__new__(TC3);d.read_metadata=Mock(return_value={'device_mode':4});d._request=Mock()
  self.assertEqual(d.read_waveform(),({'device_mode':4},[]));d._request.assert_not_called()
 def test_v2_rejects_navigation_without_key(self):
  d=TC3.__new__(TC3);d.read_metadata=Mock(return_value={'protocol_version':2});d.press_key=Mock()
  with self.assertRaises(RuntimeError):d.select_mode('tools')
  d.press_key.assert_not_called()
 def test_mode_change_requires_readback(self):
  d=TC3.__new__(TC3);d.read_metadata=Mock(return_value={'protocol_version':3,'device_mode':1,'home_selection':2});d.press_key=Mock()
  with self.assertRaises(RuntimeError):d.select_mode('generator')
 def test_invalid_mode_has_no_device_io(self):
  d=TC3.__new__(TC3);d.read_metadata=Mock()
  with self.assertRaises(ValueError):d.select_mode('poweroff')
  d.read_metadata.assert_not_called()
