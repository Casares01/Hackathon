"""The single prepared itinerary, defined by the user's latitude/longitude list."""
from copy import deepcopy


PRESETS=[dict(
    id='volcanic-traverse',
    name='Volcanic Study Traverse',
    region='Equatorial traverse',
    origin=(2.78758,-111.07354),
    description='A one-way rover planning scenario through three specified volcanic waypoints.',
    source='https://trek.nasa.gov/mars/',
    settings=dict(mission_mode='Rover',mission_speed=10.0,mission_autonomy=120.0,
                  mission_return=False,mission_slope=15.0,mission_reserve=5.0,
                  mission_walk=240.0,mission_rest=30.0),
    stops=[
        dict(name='Tharsis Montes',type='Science',lat=1.57,lon=-112.58,minutes=30.0,
             objective='Study the Tharsis Montes volcano. Log surface texture and local relief before continuing west to Pavonis Mons.'),
        dict(name='Pavonis Mons',type='Science',lat=1.48,lon=-112.96,minutes=30.0,
             objective='Repeat the surface observations from the first station. Review the remaining traverse time.'),
    ],
)]

LOCATIONS={route['region']:route['origin'] for route in PRESETS}


def preset_by_id(route_id):
    return deepcopy(next(route for route in PRESETS if route['id']==route_id))
