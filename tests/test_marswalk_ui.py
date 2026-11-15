import unittest
from unittest.mock import patch
import numpy as np
from pathlib import Path

from streamlit.testing.v1 import AppTest


class MarswalkUITests(unittest.TestCase):
    def test_viewport_update_draws_outside_route_without_editing_it(self):
        from mars_help.presets import PRESETS
        app=AppTest.from_file(str(Path(__file__).with_name('ui_fixture.py')),default_timeout=20).run()
        next(w for w in app.selectbox if w.label=='Start with a route').set_value(PRESETS[0]['id']).run()
        signature=app.session_state['eva_result']['signature']
        stops=list(app.session_state['eva_result']['stops'])
        event=dict(kind='viewport',bounds=[10,14,-134,-130],event_id='pan-outside-route')
        with patch('mars_help.marswalk.mars_map',return_value=event):
            app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['eva_result']['signature'],signature)
        self.assertEqual(app.session_state['eva_result']['stops'],stops)
        terrain=app.session_state['topography_view_'+PRESETS[0]['region']]['terrain']
        self.assertEqual(terrain['render_mode'],'shaded')
        self.assertLess(terrain['bounds'][0],10)
        self.assertGreater(terrain['bounds'][1],14)
        self.assertLess(terrain['bounds'][2],-134)
        self.assertGreater(terrain['bounds'][3],-130)

    def test_environment_view_scopes_measurements_and_optional_route_scenario(self):
        app=AppTest.from_file(str(Path(__file__).with_name('ui_fixture.py')),default_timeout=20).run()
        app.session_state['location']='Gale Crater'
        app.session_state['zone_rows_Gale Crater']=[dict(name='Survey',type='Science',lat=-4.60,lon=137.45,objective='Observe surface textures.',minutes=15.)]
        app.run()
        next(w for w in app.radio if w.label=='Resource').set_value('Weather & radiation').run()
        self.assertFalse(app.exception)
        self.assertTrue(any(m.label=='Local UV category' and m.value=='Moderate' for m in app.metric))
        self.assertTrue(any('Median observed absorbed-dose rate'==m.label for m in app.metric))
        next(w for w in app.checkbox if w.label=='Compare with the complete route duration').check().run()
        self.assertFalse(app.exception)
        result=app.session_state['eva_result']
        self.assertAlmostEqual(result['environment_scenario']['absorbed_detector_dose_ugy'],240*result['duration']/24)
        app.session_state['location']='Columbia Hills'
        app.session_state['zone_rows_Columbia Hills']=[dict(name='Survey',type='Science',lat=-14.59,lon=175.48,objective='Observe surface textures.',minutes=15.)]
        app.run()
        next(w for w in app.radio if w.label=='Resource').set_value('Weather & radiation').run()
        self.assertFalse(app.exception)
        self.assertFalse(any('Median observed absorbed-dose rate'==m.label for m in app.metric))
        self.assertNotIn('environment_scenario',app.session_state['eva_result'])
        self.assertTrue(any('No route-associated weather' in info.value for info in app.info))

    def test_topography_switch_and_point_inspection_keep_the_route(self):
        from mars_help.presets import PRESETS
        app=AppTest.from_file(str(Path(__file__).with_name('ui_fixture.py')),default_timeout=20).run()
        next(w for w in app.selectbox if w.label=='Start with a route').set_value(PRESETS[0]['id']).run()
        self.assertFalse(app.exception)
        self.assertEqual(next(w for w in app.radio if w.label=='Map view').value,'Topography')
        signature=app.session_state['eva_result']['signature']
        next(w for w in app.selectbox if w.label=='Inspect a point').set_value(0).run()
        self.assertFalse(app.exception)
        point=app.session_state['eva_result']['events'][0]
        self.assertTrue(any(point['objective'] in text.value for text in app.markdown))
        next(w for w in app.radio if w.label=='Map view').set_value('Satellite').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['eva_result']['signature'],signature)
        self.assertTrue(point['objective'])

    def test_single_preset_loads_exact_requested_waypoints_and_clear_stays_empty(self):
        from mars_help.presets import PRESETS
        app=AppTest.from_file(str(Path(__file__).with_name('ui_fixture.py')),default_timeout=20).run()
        self.assertEqual(len(PRESETS),1)
        expected=[(2.78758,-111.07354),(1.57,-112.58),(1.48,-112.96),(2.95,-121.42)]
        for preset in PRESETS:
            next(w for w in app.selectbox if w.label=='Start with a route').set_value(preset['id']).run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            result=app.session_state['eva_result']
            self.assertEqual(result['region'],preset['region'])
            self.assertEqual(len(result['stops']),3)
            self.assertNotEqual(result['route'].coordinates[0],result['route'].coordinates[-1])
            self.assertEqual([preset['origin']]+[(p['lat'],p['lon']) for p in result['stops']],expected)
            self.assertEqual(result['schedule']['travel_mode'],'Rover')
            self.assertGreaterEqual(result['margin'],0)
            self.assertEqual(app.session_state['active_preset']['id'],preset['id'])
        generation=app.session_state['map_generation']
        next(w for w in app.button if w.label=='Clear route').click().run()
        self.assertFalse(app.exception)
        self.assertNotIn('eva_result',app.session_state)
        self.assertNotIn('active_preset',app.session_state)
        self.assertEqual(app.session_state['preset_choice'],'custom')
        self.assertGreater(app.session_state['map_generation'],generation)
        app.run()
        self.assertNotIn('eva_result',app.session_state)
        next(w for w in app.radio if w.label=='Add destinations').set_value('Distance or coordinates').run()
        self.assertFalse(app.exception)
        self.assertNotIn('eva_result',app.session_state)
        next(w for w in app.toggle if w.label=='Use exact coordinates').set_value(True).run()
        self.assertFalse(app.exception)
        self.assertNotIn('eva_result',app.session_state)

    def test_main_page_has_no_volcano_mode(self):
        from mars_help.mars_elevation import MarsElevationAPI
        from mars_help.presets import PRESETS
        def terrain(**bounds):
            return np.linspace(bounds['min_lon'],bounds['max_lon'],85),np.linspace(bounds['min_lat'],bounds['max_lat'],22),np.zeros((22,85))
        with patch.object(MarsElevationAPI,'get_elevation_grid',side_effect=terrain),patch('mars_help.marswalk.load_resources',return_value={'errors':[],'geology':[],'images':{'items':[]}}):
            app=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertFalse(any('volcano' in str(widget.options).lower() for widget in app.sidebar.radio))
        self.assertEqual(app.title[0].value,'Marswalk')
        self.assertTrue(any(w.label=='Clear route' for w in app.button))
        self.assertEqual(app.session_state['active_preset']['id'],PRESETS[0]['id'])

    def test_large_numbers_and_geology_are_tied_to_numbered_route_points(self):
        app=AppTest.from_file(str(Path(__file__).with_name('ui_fixture.py')),default_timeout=20).run()
        next(w for w in app.number_input if w.label=='Speed (km/h)').set_value(200.0)
        next(w for w in app.number_input if w.label=='Autonomy (hours)').set_value(1000.0)
        next(w for w in app.number_input if w.label=='Rest duration (min)').set_value(300.0)
        next(w for w in app.number_input if w.label=='Continuous walking (min)').set_value(500.0)
        app.session_state['zone_rows_Jezero Crater']=[{'name':f'P{i}','type':'Science','lon':77.58+i*.001,'lat':18.39,'objective':'Photo','minutes':600.0} for i in range(31)]
        app.run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(len(app.session_state['eva_result']['stops']),31)
        next(w for w in app.radio if w.label=='Resource').set_value('Geology · USGS').run()
        next(w for w in app.selectbox if w.label=='Route stop').set_value(1).run()
        self.assertFalse(app.exception)
        self.assertTrue(any(metric.value=='TEST-1' for metric in app.metric))
        next(w for w in app.number_input if w.label=='Speed (km/h)').set_value(0.0).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)

    def test_points_automatically_recalculate_route_and_rests_without_radius(self):
        app=AppTest.from_file(str(Path(__file__).with_name('ui_fixture.py')),default_timeout=20).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('first destination' in element.value for element in app.info))
        self.assertFalse(any('Radio' in widget.label for widget in app.slider))
        app.session_state['zone_rows_Jezero Crater']=[{'name':'Target','type':'Science','lon':77.70,'lat':18.39,'objective':'Photo','minutes':15.0}]
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.tabs),4)
        result=app.session_state['eva_result']
        self.assertGreater(result['schedule']['rest_count'],0)
        self.assertEqual(result['route'].coordinates[0],result['route'].coordinates[-1])
        self.assertFalse(any('Create route' in button.label for button in app.button))
        app.session_state['zone_rows_Jezero Crater'].append({'name':'Science','type':'Science','lon':77.60,'lat':18.39,'objective':'Photo','minutes':20.0})
        # Result snapshots must not change when the draft list is edited.
        self.assertEqual(len(result['stops']),1)
        app.session_state['zone_revision_Jezero Crater']=1
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state['eva_result']['stops']),2)
        before=app.session_state['eva_result']['schedule']['rest_count']
        speed=next(widget for widget in app.number_input if widget.label=='Speed (km/h)')
        speed.set_value(1.0).run()
        self.assertFalse(app.exception)
        self.assertGreater(app.session_state['eva_result']['schedule']['rest_count'],before)
        self.assertLess(app.session_state['eva_result']['margin'],0)
        self.assertTrue(any('exceeds autonomy' in element.value.lower() for element in app.error))
        next(widget for widget in app.checkbox if widget.label=='Return to origin').uncheck().run()
        self.assertFalse(app.exception)
        route=app.session_state['eva_result']['route']
        self.assertNotEqual(route.coordinates[0],route.coordinates[-1])


if __name__=='__main__':
    unittest.main()
