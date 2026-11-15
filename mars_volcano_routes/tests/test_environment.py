from datetime import date
import unittest
from unittest.mock import patch

import requests

from mars_help.environment import weather_records,radiation_records,associated_points,fetch_environment,radiation_scenario,STATIONS


def cdf_fixture(units='uGray/day (good Q)'):
    def variable(attributes,data):
        return [{'VarAttributes':[{key:value} for key,value in attributes.items()]},{'VarData':data}]
    return {'fixture.cdf':{'CDFVariables':[
        {'DOSIMETRY_TOTAL_f':variable({'UNITS':units,'DEPEND_0':'EPOCH','LABL_PTR_1':'labels','FILLVAL':-1e31,'VALIDMIN':0,'VALIDMAX':100000},[[30,5],[40,6],[-1e31,7],[50,8]])},
        {'labels':variable({},['Total Dose E','Total Dose B'])},
        {'EPOCH':variable({},['2026-01-01T00:00:00Z','2026-01-01T00:15:00Z','2026-01-01T00:30:00Z','2027-01-01T00:00:00Z'])},
        {'FLAGGED_DATA':variable({},['   ','Cmds','   ','   '])},
    ]}}


class EnvironmentTests(unittest.TestCase):
    def test_weather_sorts_dates_and_does_not_treat_missing_as_zero(self):
        result=weather_records({'soles':[
            dict(terrestrial_date='2026-01-02',sol='2',min_temp='-70',max_temp='-5',pressure='777',wind_speed='--',local_uv_irradiance_index='Moderate'),
            dict(terrestrial_date='2026-01-01',sol='1',min_temp='--',max_temp='--',pressure='700'),
            dict(terrestrial_date='2027-01-01',sol='99',pressure='800'),
        ]},date(2026,11,14))
        self.assertEqual(result[-1]['date'],'2026-01-02')
        self.assertIsNone(result[-1]['wind_ms'])
        self.assertEqual(result[-1]['uv_category'],'Moderate')
        self.assertIsNone(result[0]['air_min_c'])

    def test_meda_uses_its_own_schema_and_does_not_reuse_another_sols_temperature(self):
        result=weather_records({'sols':[
            dict(terrestrial_date='2024-04-25',sol='1',min_temp=-70,max_temp=-20,pressure=777),
            dict(terrestrial_date='2024-04-26',sol='2',min_temp='--',max_temp='--',pressure=778),
            dict(terrestrial_date='2024-04-27',sol='3',min_temp='--',max_temp='--',pressure='--'),
        ]})
        self.assertEqual(result[-1]['date'],'2024-04-26')
        self.assertIsNone(result[-1]['air_min_c'])
        self.assertIsNone(result[-1]['uv_category'])

    def test_rad_channel_comes_from_labels_and_rejects_flagged_fill_and_future_samples(self):
        result=radiation_records(cdf_fixture(),date(2026,11,14))
        self.assertEqual(result,[{'time':'2026-01-01T00:00:00Z','dose_rate_ugy_day':30.0}])

    def test_unknown_radiation_units_are_not_silently_converted(self):
        with self.assertRaises(ValueError):
            radiation_records(cdf_fixture('mSv/day'),date(2026,11,14))

    def test_spatial_association_does_not_transfer_gale_observations_to_jezero(self):
        points=[dict(route_id='H',lon=77.39,lat=18.45),dict(route_id='1',lon=137.44,lat=-4.59)]
        self.assertEqual(associated_points(points,STATIONS['msl']),['1'])
        self.assertEqual(associated_points(points,STATIONS['mars2020']),['H'])

    @patch('mars_help.environment.fetch_radiation',side_effect=requests.Timeout('offline'))
    @patch('mars_help.environment.fetch_weather',return_value={'latest':{'date':'2026-01-01'}})
    def test_radiation_outage_does_not_discard_weather(self,*_):
        result=fetch_environment([dict(route_id='H',lon=137.44,lat=-4.59)])
        self.assertEqual(len(result['weather']),1)
        self.assertEqual(result['weather'][0]['route_point_ids'],['H'])
        self.assertIsNone(result['radiation'])
        self.assertEqual(result['errors'][0]['resource'],'radiation')

    @patch('mars_help.environment.requests.get')
    def test_uncovered_route_does_not_fetch_unrelated_measurements(self,get):
        result=fetch_environment([dict(route_id='H',lon=175.47,lat=-14.58)])
        self.assertEqual(result['weather'],[])
        self.assertIsNone(result['radiation'])
        get.assert_not_called()

    def test_optional_scenario_uses_route_hours_and_never_converts_grays_to_sieverts(self):
        reference=dict(whole_itinerary_associated=True,median_ugy_day=240,date='2026-01-01')
        self.assertEqual(radiation_scenario(reference,6)['absorbed_detector_dose_ugy'],60)
        self.assertIsNone(radiation_scenario(dict(reference,whole_itinerary_associated=False),6))
        self.assertIn('Not a forecast',radiation_scenario(reference,6)['assumption'])


if __name__=='__main__':
    unittest.main()
