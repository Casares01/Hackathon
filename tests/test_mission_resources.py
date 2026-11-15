import json
import unittest
from unittest.mock import Mock, patch

import requests

from mars_help.mission_resources import fetch_resources, geology_at, geology_for_event, resource_manifest, regional_images


class MissionResourcesTests(unittest.TestCase):
    @patch('mars_help.mission_resources.requests.get')
    def test_geology_uses_mars_reference_system_and_coordinates(self, get):
        get.return_value = Mock(json=lambda:{'features':[{'attributes':{'Unit':'HNt'}}]})
        point={'name':'Rest','lon':77.58,'lat':18.38}
        result=geology_at(point)
        params=get.call_args.kwargs['params']
        geometry=json.loads(params['geometry'])
        self.assertEqual(geometry['x'],77.58)
        self.assertIn('Mars',geometry['spatialReference']['wkt'])
        self.assertNotIn('4326',params['inSR'])
        self.assertEqual(result['units'][0]['Unit'],'HNt')

    @patch('mars_help.mission_resources.requests.get')
    def test_far_away_region_does_not_attach_unrelated_photos(self,get):
        self.assertEqual(regional_images('Jezero Crater',{'lon':0,'lat':0})['items'],[])
        get.assert_not_called()

    @patch('mars_help.mission_resources.geology_at',return_value={'name':'Science','units':[]})
    @patch('mars_help.mission_resources.regional_images',return_value={'items':[]})
    @patch('mars_help.mission_resources.themis_image',side_effect=requests.Timeout('offline'))
    def test_resource_failure_keeps_other_results(self,*_):
        bundle=fetch_resources((0,1,0,1),[{'name':'Science','lon':0,'lat':0}],'Jezero Crater',{'lon':0,'lat':0})
        self.assertEqual(len(bundle['geology']),1)
        self.assertEqual(bundle['errors'][0]['resource'],'themis')
        self.assertIn('retrieved_at',bundle)

    def test_export_keeps_provenance_without_embedded_raster(self):
        manifest=resource_manifest({'themis':{'image':'data:image/png;base64,abc','source':'USGS'},'geology':[]})
        self.assertNotIn('image',manifest['themis'])
        self.assertEqual(manifest['themis']['source'],'USGS')

    def test_geology_matches_route_id_and_actual_location(self):
        bundle={'geology':[{'route_id':'1','lon':0,'lat':0,'name':'Wrong place'},{'route_id':'1','lon':1,'lat':2,'name':'Correct place'},{'route_id':'2','lon':1,'lat':2,'name':'Return visit'}]}
        self.assertEqual(geology_for_event(bundle,{'route_id':'2','lon':1,'lat':2})['name'],'Return visit')
        self.assertEqual(geology_for_event(bundle,{'route_id':'1','lon':1,'lat':2})['name'],'Correct place')
        self.assertIsNone(geology_for_event(bundle,{'route_id':'1','lon':9,'lat':9}))


if __name__=='__main__':
    unittest.main()
