import unittest
from fnirsi_tc3.scope import Scope

class ZoomTests(unittest.TestCase):
    def scope(self):
        scope=Scope.__new__(Scope)
        scope.zoom_x=scope.zoom_y=1.
        scope.pan_x=scope.pan_y=0.
        scope.samples=[];scope.metadata={};scope.draw=lambda:None
        return scope
    def test_zoom_limits_and_reset(self):
        s=self.scope();s.zoom(1000,1000)
        self.assertEqual((s.zoom_x,s.zoom_y),(100,100))
        s.pan_x=9;s.pan_y=8;s.reset_zoom()
        self.assertEqual((s.zoom_x,s.zoom_y,s.pan_x,s.pan_y),(1,1,0,0))
    def test_pointer_anchor_is_preserved(self):
        s=self.scope();s.plot_bounds=(0,0,100,100);s.view_bounds=(0,100,-50,50)
        s.zoom(2,2,(75,25))
        self.assertEqual((s.pan_x,s.pan_y),(12.5,12.5))
    def test_ripple_centring_preserves_samples(self):
        s=self.scope();s.samples=[48,50,52]*200
        s.metadata={'measurements':True,'offset_raw':0,'trigger_sample':100}
        original=s.samples.copy();s.centre_ripple()
        self.assertEqual(s.pan_y,50)
        self.assertGreater(s.zoom_y,30)
        self.assertEqual(s.samples,original)
