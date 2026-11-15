import unittest
import numpy as np
from mars_help.viewport_topography import view_bounds,padded_view_bounds,covers,load_view_grid


class ViewportTopographyTests(unittest.TestCase):
    def test_padding_covers_visible_area_and_clamps_planet(self):
        self.assertTrue(covers(padded_view_bounds((1,3,-121,-111)),(1,3,-121,-111)))
        self.assertEqual(view_bounds((-100,100,-200,200)),(-89.999,89.999,-179.999,179.999))

    def test_world_view_splits_profiles_without_duplicate_seams(self):
        calls=[]
        def loader(s,n,w,e):
            calls.append((w,e))
            xs=np.linspace(w,e,5);ys=np.linspace(s,n,3)
            return xs,ys,np.tile(xs,(3,1))
        xs,ys,z=load_view_grid(loader,(-80,80,-179,179))
        self.assertEqual(len(calls),4)
        self.assertTrue(all(e-w<=90 for w,e in calls))
        self.assertTrue(np.all(np.diff(xs)>0))
        self.assertEqual(z.shape,(3,17))
        np.testing.assert_array_equal(z[0],xs)

    def test_invalid_view_rejected(self):
        for bounds in [(1,1,2,3),(0,1,float('nan'),2),(0,1,200,210)]:
            with self.assertRaises(ValueError):view_bounds(bounds)
