import base64
from io import BytesIO
import unittest

import numpy as np
from PIL import Image

from mars_help.topography import terrain_overlay
from mars_help.point_details import enrich_point_context,point_objective
from mars_help.mission_planning import schedule_route


class TopographyAndPointTests(unittest.TestCase):
    def test_route_contours_do_not_cover_the_surrounding_basemap(self):
        result=terrain_overlay([1,2],[3,4],[[0,0],[100,100]],contours_only=True)
        image=np.asarray(Image.open(BytesIO(base64.b64decode(result['image'].split(',')[1]))))
        self.assertEqual(result['render_mode'],'contours')
        self.assertTrue(result['has_contours'])
        self.assertEqual(image[10,10,3],0)
        self.assertGreater(np.mean(image[:,:,3]==0),.5)
        self.assertGreater(np.max(image[:,:,3]),0)

    def test_topographic_overlay_preserves_north_and_measured_elevation(self):
        result=terrain_overlay([1,2],[3,4],[[0,0],[100,100]])
        image=np.asarray(Image.open(BytesIO(base64.b64decode(result['image'].split(',')[1]))))
        self.assertEqual(result['bounds'],[3,4,1,2])
        self.assertEqual(result['minimum_m'],0)
        self.assertEqual(result['maximum_m'],100)
        self.assertGreater(int(image[10,10,0]),int(image[-10,10,0]))
        self.assertGreater(result['contour_interval_m'],0)

    def test_flat_and_missing_terrain_do_not_invent_elevations(self):
        result=terrain_overlay([0,1],[0,1],[[42,42],[42,np.nan]])
        self.assertEqual(result['minimum_m'],42)
        self.assertEqual(result['maximum_m'],42)
        with self.assertRaises(ValueError):
            terrain_overlay([0,1],[0,1],np.full((2,2),np.nan))

    def test_requested_point_is_preserved_and_grid_adjustment_is_reported(self):
        schedule=schedule_route([(0,0),(.1,.1)],[dict(name='Survey',type='Science',lon=.09,lat=.09,minutes=15,objective='Photograph bedding at two scales.')],[1],speed=2,autonomy=8,reserve=25)
        enrich_point_context(schedule,[0,.1],[0,.1],np.array([[10,20],[30,40]]))
        target=schedule['events'][-1]
        self.assertEqual(target['requested_lon'],.09)
        self.assertEqual(target['elevation_m'],40)
        self.assertGreater(target['grid_offset_m'],0)
        self.assertEqual(point_objective(target),'Photograph bedding at two scales.')
        rest=next(point for point in schedule['events'] if point['automatic'])
        self.assertIn('60 minutes of walking',rest['objective'])
        self.assertIn('10-minute break',rest['objective'])


if __name__=='__main__':
    unittest.main()
