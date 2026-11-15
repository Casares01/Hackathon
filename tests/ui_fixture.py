"""Deterministic UI harness: no calls to external providers."""
import numpy as np
import base64
import streamlit as st
from io import BytesIO
from PIL import Image
from mars_help import marswalk
from mars_help.environment import STATIONS


def elevation(south,north,west,east):
    return np.linspace(west,east,25),np.linspace(south,north,25),np.zeros((25,25))


def resources(bounds,points,*args):
    buffer=BytesIO()
    Image.fromarray(np.array([[30,80],[180,240]],dtype=np.uint8)).save(buffer,format='PNG')
    environment=dict(weather=[],radiation=None,errors=[])
    region=args[0]
    ids=[point['route_id'] for point in points]
    if region in ('Gale Crater','Jezero Crater'):
        station=STATIONS['msl' if region=='Gale Crater' else 'mars2020']
        record=dict(date='2020-01-01',sol='1',air_min_c=-70.,air_max_c=-5.,pressure_pa=777.,wind_ms=None,ground_min_c=None,ground_max_c=None,uv_category='Moderate' if region=='Gale Crater' else None)
        environment['weather']=[dict(instrument=station['name'],station=station,latest=record,records=[record],route_point_ids=ids,source='https://mars.nasa.gov/rss/api/',use='Test fixture only')]
        if region=='Gale Crater':
            environment['radiation']=dict(instrument='Curiosity / RAD',date='2020-01-01',channel='Detector E · tissue-equivalent plastic',median_ugy_day=240.,whole_itinerary_associated=True,records=[dict(time='2020-01-01T00:00:00Z',dose_rate_ugy_day=240.)],quality='Fixture only',route_point_ids=ids,use='Test fixture only',source='https://cdaweb.gsfc.nasa.gov/',archive='https://spdf.gsfc.nasa.gov/')
    return {'environment':environment,'themis':{'image':'data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode(),'bounds':list(bounds),'source':'https://pubs.usgs.gov/sim/3292/','label':'Test mosaic only','coverage':'Fixture only'},'geology':[dict(route_id=p.get('route_id'),name=p['name'],lon=p['lon'],lat=p['lat'],units=[{'Unit':'TEST-'+str(p.get('route_id')),'UnitDesc':'Test unit','Interpretation':'Fixture only'}],source='https://pubs.usgs.gov/sim/3292/',scale='Test scale') for p in points], 'errors':[], 'images':{'items':[],'coverage':'Test context'}}


marswalk.load_resources=resources
st.session_state.setdefault('route_schema',3)
st.session_state.setdefault('preset_choice','custom')
st.session_state.setdefault('location','Jezero Crater')
marswalk.render(elevation,{'Jezero Crater':(18.38,77.58),'Gale Crater':(-4.59,137.44),'Columbia Hills':(-14.58,175.47)})
