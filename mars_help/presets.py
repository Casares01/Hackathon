"""Five editable science-inspired itineraries, not verified rover traverses."""
from copy import deepcopy


def stop(name,lon,lat,objective,minutes=15.0):
    return dict(name=name,type='Science',lon=lon,lat=lat,objective=objective,minutes=minutes)


PRESETS = [
    dict(id='jezero',name='Jezero · Ancient Delta',region='Jezero Crater',origin=(18.45,77.39),
         description='Trace the story of an ancient river delta.',
         source='https://science.nasa.gov/resource/perseverance-explores-the-jezero-crater-delta/',
         stops=[stop('Delta context panorama',77.395,18.455,'Take a wide panorama to document the proposed station in relation to the delta landscape and crater floor.'),stop('Surface texture comparison',77.405,18.46,'Photograph nearby exposed surfaces at a consistent scale. Log differences in texture and any visible layering.'),stop('Crater-floor perspective',77.415,18.455,'Capture a second panorama and compare apparent relief with the first station. Record observation directions in the mission log.')]),
    dict(id='gale',name='Gale · Layers of Time',region='Gale Crater',origin=(-4.59,137.44),
         description='Survey Gale crater-floor terrain in the context of Mount Sharp.',
         source='https://science.nasa.gov/resource/the-making-of-mount-sharp/',
         stops=[stop('Crater-floor context',137.445,-4.595,'Photograph the surrounding crater-floor terrain. Record how exposed rock, loose material and local relief vary around the station.'),stop('Rock texture log',137.455,-4.60,'Use close-up photographs to compare rock textures with the first station. Log visible layering without assuming a rock composition.'),stop('Mount Sharp context panorama',137.465,-4.595,'Take a horizon panorama toward the Mount Sharp region where visible. Link the image directions to the route map for later comparison.')]),
    dict(id='columbia',name='Columbia Hills · Water Clues',region='Columbia Hills',origin=(-14.58,175.47),
         description='Investigate the landscape explored by Spirit.',
         source='https://science.nasa.gov/mission/mer-spirit/',
         stops=[stop('Hillside context station',175.475,-14.585,'Record a panorama of the hill surroundings and note changes in apparent slope along the planned approach.'),stop('Surface alteration survey',175.48,-14.59,'Photograph contrasting surface textures and colours for later comparison with Spirit science results. Imagery alone does not identify minerals.'),stop('Terrain comparison panorama',175.49,-14.585,'Capture a second view of the hills and compare the exposed surfaces and relief with the earlier stations.')]),
    dict(id='victoria',name='Victoria · Crater Stories',region='Victoria Crater',origin=(-2.035,-5.515),
         description='Explore the impact landscape visited by Opportunity.',
         source='https://science.nasa.gov/photojournal/victoria-crater-at-meridiani-planum/',
         stops=[stop('Impact-landscape context',-5.51,-2.037,'Photograph the terrain surrounding Victoria and mark the crater direction in the mission log. This station is a proposed observation location.'),stop('Surface material comparison',-5.50,-2.038,'Compare loose material and exposed rock with the first station using photographs taken at a consistent scale.'),stop('Victoria context panorama',-5.49,-2.04,'Capture a wide panorama toward the crater where visible. Document apparent relief without assuming rim access or a safe viewpoint.')]),
    dict(id='ares',name='Ares Vallis · Floodplain Explorer',region='Ares Vallis',origin=(19.13,-33.22),
         description='Explore the ancient floodplain of the Pathfinder region.',
         source='https://science.nasa.gov/mission/mars-pathfinder/',
         stops=[stop('Floodplain context station',-33.215,19.135,'Take a panorama of the Pathfinder-region floodplain and log the distribution of visible rocks and loose surface material.'),stop('Rock-shape comparison',-33.205,19.14,'Photograph several visible rocks at a consistent scale. Compare shape and texture without inferring composition from appearance.'),stop('Floodplain comparison panorama',-33.195,19.135,'Record a second landscape panorama and compare rock distribution and apparent surface relief with the first station.')]),
]

LOCATIONS = {route['region']:route['origin'] for route in PRESETS}


def preset_by_id(route_id):
    return deepcopy(next(route for route in PRESETS if route['id']==route_id))
