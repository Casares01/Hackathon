import unittest

from mars_help.mission_planning import bounds_for_points, schedule_route


class MissionPlanningTests(unittest.TestCase):
    def schedule(self,length=5000,**kwargs):
        return schedule_route([(0.,0.),(.1,0.)],[],[],speed=kwargs.pop('speed',1),autonomy=kwargs.pop('autonomy',8),reserve=0,continuous_minutes=60,rest_minutes=10,edge_distances=[length],**kwargs)

    def test_bounds_follow_points_far_beyond_old_radius(self):
        south,north,west,east=bounds_for_points(0,0,[{'lon':20,'lat':10}])
        self.assertLess(south,0); self.assertGreater(north,10)
        self.assertLess(west,0); self.assertGreater(east,20)

    def test_rests_interpolate_inside_long_edge_and_consume_budget(self):
        result=self.schedule()
        self.assertEqual(result['rest_count'],4)
        self.assertEqual([round(e['lon'],2) for e in result['events']],[.02,.04,.06,.08])
        self.assertAlmostEqual(result['duration_h'],(300+40)/60)
        self.assertAlmostEqual(result['margin_h'],8-(300+40)/60)
        self.assertEqual([round(e['arrival_min']) for e in result['events']],[60,130,200,270])

    def test_no_unnecessary_rest_on_arrival(self):
        self.assertEqual(self.schedule(length=1000)['rest_count'],0)
        self.assertEqual(self.schedule(length=2000)['rest_count'],1)

    def test_velocity_and_autonomy_change_rest_distribution(self):
        self.assertLess(self.schedule(speed=2)['rest_count'],self.schedule(speed=1)['rest_count'])
        self.assertGreater(self.schedule(autonomy=2)['rest_count'],self.schedule(autonomy=8)['rest_count'])
        self.assertLess(self.schedule(autonomy=2)['margin_h'],0)

    def test_manual_rest_resets_cadence_and_avoids_duplicate(self):
        result=schedule_route([(0,0),(.1,0),(.2,0)],[{'name':'Rest','type':'Rest','minutes':10}],[1],speed=1,autonomy=8,reserve=0,edge_distances=[1000,1000])
        self.assertEqual(result['rest_count'],0)
        self.assertAlmostEqual(result['duration_h'],130/60)

    def test_return_leg_also_gets_rest_stops(self):
        result=schedule_route([(0,0),(.1,0),(0,0)],[],[],speed=1,autonomy=8,reserve=0,edge_distances=[1500,1500])
        self.assertEqual(result['rest_count'],2)
        self.assertAlmostEqual(result['events'][1]['lon'],.1*(1-500/1500))


if __name__=='__main__':
    unittest.main()
