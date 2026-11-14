"""Local Marswalk planning UI reusing the existing terrain route solver."""
import base64
import csv
import io
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from mars_help.terrain_routes import Waypoint, plan_terrain_route, distance_m
from mars_help.mission_resources import fetch_resources, resource_manifest
from mars_help.mission_planning import bounds_for_points, schedule_route
from mars_help.route_views import render_route_resources
from mars_help.presets import PRESETS, LOCATIONS as PRESET_LOCATIONS, preset_by_id
from mars_help.topography import terrain_overlay
from mars_help.point_details import ZONE_OBJECTIVES, point_objective, enrich_point_context
from mars_help.route_views import render_point_inspector

mars_map = components.declare_component('mars_coordinate_picker', path=str(Path(__file__).parent / 'map_picker'))
load_resources = st.cache_data(ttl=3600, show_spinner=False)(fetch_resources)
load_terrain_overlay = st.cache_data(ttl=3600,show_spinner=False)(terrain_overlay)
ZONE_TYPES = {'Science':'#a356c9', 'Rest':'#2b91a0', 'Landing':'#d69226', 'Habitat':'#31825b', 'Communications':'#4d73c5'}


def clear_route(reset_selection=True):
    """Remove drafts, derived results, imported layers and stale map events."""
    prefixes=('zone_rows_','zone_revision_','zone_editor_','zone_name_','eva_stops_','eva_simple_','manual_','extra_layer_')
    for key in list(st.session_state):
        if key.startswith(prefixes) or key in ('eva_result','eva_attempt','eva_error','active_preset','inspect_point','radiation_duration_scenario'):
            del st.session_state[key]
    st.session_state['map_generation']=st.session_state.get('map_generation',0)+1
    if reset_selection:
        st.session_state['preset_choice']='custom'


def load_preset():
    route_id=st.session_state['preset_choice']
    clear_route(reset_selection=False)
    if route_id=='custom':
        return
    route=preset_by_id(route_id)
    region=route['region']
    st.session_state['location']=region
    st.session_state['eva_lat_'+region]=route['origin'][0]
    st.session_state['eva_lon_'+region]=route['origin'][1]
    st.session_state['zone_rows_'+region]=route['stops']
    st.session_state['active_preset']=route
    st.session_state.update(mission_speed=2.0,mission_autonomy=8.0,mission_return=True,mission_slope=30.0,mission_reserve=25.0,mission_walk=60.0,mission_rest=10.0,entry_mode='On the map')


def set_origin(region, point):
    st.session_state['eva_lat_'+region] = float(point['lat'])
    st.session_state['eva_lon_'+region] = float(point['lon'])


def location_changed():
    st.session_state.pop('active_preset',None)
    st.session_state['preset_choice']='custom'


def zone_markers(stops, lon, lat):
    return [{'lon':lon,'lat':lat,'name':'Mission origin','type':'Habitat','color':ZONE_TYPES['Habitat'],'label':'H','objective':'Starting point for this plan. Return travel is included only when enabled.'}]+[
        {'lon':p['lon'],'lat':p['lat'],'name':p['name'],'type':p.get('type','Science'),'color':ZONE_TYPES.get(p.get('type'),ZONE_TYPES['Science']),'label':str(i),'objective':point_objective(p),'detail':f"{p.get('distance_km',0):.2f} km from origin · arrival {p.get('arrival_min',0):.0f} min · {p.get('minutes',0):g} min on site" if 'arrival_min' in p else ''} for i,p in enumerate(stops,1) if isinstance(p.get('lon'),(int,float)) and isinstance(p.get('lat'),(int,float)) and math.isfinite(p['lon']) and math.isfinite(p['lat'])]


def map_stops(region, lon, lat):
    rows_key = 'zone_rows_'+region
    revision_key = 'zone_revision_'+region
    if rows_key not in st.session_state:
        st.session_state[rows_key] = []
    rows = st.session_state[rows_key]
    saved = st.session_state.get('eva_result')
    current = bool(saved and saved.get('events') is not None and saved.get('region')==region and saved['lon']==lon and saved['lat']==lat and saved['stops']==rows)
    shown = saved['events'] if current else rows
    view=st.radio('Map view',['Topography','Satellite'],horizontal=True,key='map_view',label_visibility='collapsed')
    terrain=load_terrain_overlay(saved['xs'],saved['ys'],saved['z']) if current and view=='Topography' else None
    focus=None
    selected=st.session_state.get('inspect_point')
    if current and isinstance(selected,int) and 0<=selected<len(shown):
        p=shown[selected];focus=dict(lat=p['lat'],lon=p['lon'],name=f"{p.get('route_id',selected+1)} · {p['name']}")
    clicked = mars_map(center={'lon':lon,'lat':lat},points=zone_markers(shown,lon,lat),route=saved['route'].coordinates if current else [],basemap=view.lower(),raster=terrain,terrain=terrain,focus=focus,zoom=11,key=f"picker_{region}_{st.session_state.get('map_generation',0)}",default=None)
    if clicked:
        st.caption(f"{clicked['lat']:.5f}° · {clicked['lon']:.5f}°")
        action, kind, duration = st.columns([2,2,1])
        zone_type = kind.selectbox('Zone type',list(ZONE_TYPES),key='zone_kind')
        minutes = duration.number_input('Minutes',value=15.0,key='zone_minutes')
        names={'Science':'Observation station','Rest':'Rest stop','Landing':'Proposed landing zone','Habitat':'Habitat waypoint','Communications':'Communications check'}
        name = action.text_input('Point name',value=f'{names[zone_type]} {len(rows)+1}',key=f'zone_name_{region}_{len(rows)}_{zone_type}')
        objective=st.text_area('Planned activity',value=ZONE_OBJECTIVES[zone_type],key=f'zone_name_objective_{region}_{zone_type}',height=90)
        add,origin = st.columns(2)
        origin.button('Set as origin',on_click=set_origin,args=(region,clicked),width="stretch")
        if add.button('Add destination',type='primary',width='stretch'):
            if not name.strip():
                st.error('Enter a zone name.')
            elif not math.isfinite(minutes) or minutes<0:
                st.error('Duration must be a finite number greater than or equal to zero.')
            else:
                rows.append({'name':name.strip(),'type':zone_type,'lon':float(clicked['lon']),'lat':float(clicked['lat']),'objective':objective.strip() or ZONE_OBJECTIVES[zone_type],'minutes':float(minutes)})
                st.session_state[revision_key] = st.session_state.get(revision_key,0)+1
                st.rerun()
    st.markdown(' &nbsp; '.join(f'<span style="color:{color}">● {name}</span>' for name,color in ZONE_TYPES.items()),unsafe_allow_html=True)
    if not rows:
        st.info('Click the map to add your first destination.')
        return []
    with st.expander(f'Edit destinations · {len(rows)}'):
        edited = st.data_editor(rows,num_rows='dynamic',key=f"zone_editor_{region}_{st.session_state.get(revision_key,0)}",width="stretch",
            column_config={'name':st.column_config.TextColumn('Zone',required=True),'type':st.column_config.SelectboxColumn('Type',options=list(ZONE_TYPES),required=True),'lon':st.column_config.NumberColumn('Longitude (°)',required=True,format='%.5f'),'lat':st.column_config.NumberColumn('Latitude (°)',required=True,format='%.5f'),'objective':'Activity','minutes':st.column_config.NumberColumn('Duration (min)',required=True)})
    st.session_state[rows_key] = edited
    return edited


def budget(distance, speed, science_minutes, autonomy, reserve):
    values = (distance, speed, science_minutes, autonomy, reserve)
    if not all(math.isfinite(v) for v in values) or distance < 0 or speed <= 0 or science_minutes < 0 or autonomy <= 0 or not 0 <= reserve < 100:
        raise ValueError("Invalid autonomy parameters")
    duration = distance / 1000 / speed + science_minutes / 60
    usable = autonomy * (1 - reserve / 100)
    return duration, usable, usable - duration


def read_layer(raw, bounds):
    rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    if not rows or not {'lon', 'lat', 'value'} <= rows[0].keys():
        raise ValueError('CSV requires lon,lat,value columns and at least one sample.')
    points = np.array([[float(row[k]) for k in ('lon', 'lat', 'value')] for row in rows])
    if not np.isfinite(points).all():
        raise ValueError('The layer contains non-finite values.')
    points[:, 0] = (points[:, 0] + 180) % 360 - 180
    south, north, west, east = bounds
    selected = points[(points[:, 0] >= west) & (points[:, 0] <= east) & (points[:, 1] >= south) & (points[:, 1] <= north)]
    if not len(selected):
        raise ValueError('No samples fall within the mission area.')
    return selected



DIRECTIONS = {'North':0,'Northeast':45,'East':90,'Southeast':135,'South':180,'Southwest':225,'West':270,'Northwest':315}


def local_stops(rows, lon, lat):
    result = []
    for row in rows:
        distance = float(row['distance'])
        if not math.isfinite(distance) or distance <= 0:
            raise ValueError('Invalid distance')
        bearing = math.radians(DIRECTIONS[row['direction']])
        angular = distance*1000/3390000
        phi = math.radians(lat)
        target_lat = math.asin(math.sin(phi)*math.cos(angular)+math.cos(phi)*math.sin(angular)*math.cos(bearing))
        target_lon = math.radians(lon)+math.atan2(math.sin(bearing)*math.sin(angular)*math.cos(phi),math.cos(angular)-math.sin(phi)*math.sin(target_lat))
        result.append(dict(name=row['name'],lon=(math.degrees(target_lon)+180)%360-180,lat=math.degrees(target_lat),objective=row['objective'],minutes=row['minutes']))
    return result


def format_hours(hours):
    minutes = round(abs(hours)*60)
    return ('−' if hours < 0 else '') + f'{minutes//60} h {minutes%60:02d} min'


def render_resources(region):
    with st.expander('Explore NASA and USGS sources'):
        st.caption('THEMIS imagery, stop-specific USGS geology and regional NASA photos are attached automatically.')
        st.link_button('Explore Mars · Mars Trek','https://trek.nasa.gov/mars/')
        st.link_button('Geological maps · USGS / NASA','https://astrogeology-usgs.hub.arcgis.com/pages/interactive-maps-mars')
        st.link_button('Curiosity route reference · Mount Sharp','https://science.nasa.gov/resource/curiositys-proposed-path-up-mount-sharp/')
        st.link_button('Perseverance photos · Jezero','https://mars.nasa.gov/mars2020/multimedia/raw-images/')
        st.link_button('NASA Worldview · Earth-map reference','https://worldview.earthdata.nasa.gov/')
        st.caption('Worldview shows Earth; it is a visual reference, not a Mars layer.')


def render(load_elevation, locations):
    locations={**PRESET_LOCATIONS,**locations}
    if st.session_state.get('route_schema')!=2:
        clear_route()
        st.session_state['route_schema']=2
    st.markdown('''<style>
      .block-container{padding-top:1.7rem;padding-bottom:2rem;max-width:1500px}
      h1{letter-spacing:-.045em;font-weight:750!important}h3{letter-spacing:-.02em}
      [data-testid="stSidebar"]{border-right:1px solid #dfe6ed}
      [data-testid="stMetric"]{background:white;border:1px solid #e1e7ed;border-radius:10px;padding:15px 18px}
      [data-testid="stMetricLabel"]{font-size:12px;color:#64748b}
      [data-testid="stMetricValue"]{font-size:25px;font-variant-numeric:tabular-nums}
      [data-baseweb="tab-list"]{gap:26px;border-bottom:1px solid #dfe6ed}
      [data-baseweb="tab"]{padding:11px 0;font-weight:600}
      .mission-label{font:600 11px system-ui;letter-spacing:.16em;color:#64748b;margin:0 0 4px}
    </style>''',unsafe_allow_html=True)
    st.markdown('<div class="mission-label">MARS SURFACE OPERATIONS</div>',unsafe_allow_html=True)
    st.title('Marswalk')
    st.caption('Terrain, mission timing and science in one planning workspace.')
    st.sidebar.subheader('Mission setup')
    presets,reset=st.sidebar.columns([3,2],vertical_alignment='bottom')
    names={route['id']:route['name'] for route in PRESETS}
    presets.selectbox('Start with a route',['custom']+list(names),format_func=lambda value:names.get(value,'Custom route'),key='preset_choice',on_change=load_preset)
    reset.button('Clear route',on_click=clear_route,width='stretch')
    active=st.session_state.get('active_preset')
    if active:
        st.sidebar.caption(active['description'])
        with st.sidebar.expander('Mission background'):
            st.caption('Editable planning proposal, not a verified rover track.')
            st.link_button('NASA science background',active['source'])
    place=st.sidebar
    a,b=st.sidebar,st.sidebar
    c=st.sidebar
    region = place.selectbox('Location', list(locations),key='location',on_change=location_changed)
    lat, lon = locations[region]
    st.session_state.setdefault('eva_lat_'+region,float(lat))
    st.session_state.setdefault('eva_lon_'+region,(float(lon)+180)%360-180)
    defaults=dict(mission_speed=2.0,mission_autonomy=6.0,mission_return=True,mission_slope=15.0,mission_reserve=25.0,mission_walk=60.0,mission_rest=10.0)
    for key,value in defaults.items():
        st.session_state.setdefault(key,value)
    speed = a.number_input('Speed (km/h)',value=None,key='mission_speed')
    autonomy = b.number_input('Autonomy (hours)',value=None,key='mission_autonomy')
    return_home = c.checkbox('Return to origin',key='mission_return')
    with st.sidebar.expander('Route constraints'):
        left, right = st.columns(2)
        lat = left.number_input('Origin latitude (°)', value=None, key='eva_lat_'+region, format='%.5f')
        lon = right.number_input('Origin longitude (°)', value=None, key='eva_lon_'+region, format='%.5f')
        if lat is None or lon is None:
            st.info('Enter an origin or choose a region.')
            return
        slope = st.number_input('Maximum sampled slope (%)',value=None,key='mission_slope')
        reserve = st.number_input('Autonomy reserve (%)',value=None,key='mission_reserve')
        continuous_minutes = st.number_input('Continuous walking (min)',value=None,key='mission_walk')
        rest_minutes = st.number_input('Rest duration (min)',value=None,key='mission_rest')
    valid = all(v is not None and math.isfinite(v) for v in (lat,lon,speed,autonomy,slope,reserve,continuous_minutes,rest_minutes))
    if not valid or not -90<=lat<=90 or speed<=0 or autonomy<=0 or slope<0 or not 0<=reserve<100 or continuous_minutes<=0 or rest_minutes<=0:
        st.error('Check the values: valid coordinates, positive speed and times, and reserve ≥ 0 and < 100%.')
        return
    lon=(lon+180)%360-180
    entry_mode = st.sidebar.radio('Add destinations', ['On the map', 'Distance or coordinates'],horizontal=True,key='entry_mode')
    if entry_mode == 'On the map':
        stops = map_stops(region,lon,lat)
    else:
        custom = st.toggle('Use exact coordinates', help='You can also enter distance and direction.')
        if custom:
            frame=pd.DataFrame({'name':pd.Series(dtype='str'),'lon':pd.Series(dtype='float'),'lat':pd.Series(dtype='float'),'objective':pd.Series(dtype='str'),'minutes':pd.Series(dtype='float')})
            edited = st.data_editor(frame,num_rows='dynamic',key='eva_stops_'+region,width='stretch',column_config={'name':st.column_config.TextColumn('Stop',required=True),'lon':st.column_config.NumberColumn('Longitude (°)',required=True,format='%.5f'),'lat':st.column_config.NumberColumn('Latitude (°)',required=True,format='%.5f'),'objective':'Activity','minutes':st.column_config.NumberColumn('Time (min)',required=True)})
            stops=edited.to_dict('records')
        else:
            frame=pd.DataFrame({'name':pd.Series(dtype='str'),'distance':pd.Series(dtype='float'),'direction':pd.Series(dtype='str'),'objective':pd.Series(dtype='str'),'minutes':pd.Series(dtype='float')})
            edited=st.data_editor(frame,num_rows='dynamic',key='eva_simple_'+region,width='stretch',column_config={'name':st.column_config.TextColumn('Stop',required=True),'distance':st.column_config.NumberColumn('Distance (km)',required=True),'direction':st.column_config.SelectboxColumn('Direction',options=list(DIRECTIONS),required=True),'objective':'Activity','minutes':st.column_config.NumberColumn('Time (min)',required=True)})
            rows=edited.to_dict('records')
            try:
                stops = local_stops(rows,lon,lat)
            except (ValueError,TypeError,KeyError):
                stops = []
                st.warning('Complete the distance and direction for each stop.')
    st.caption(f'{len(stops)} destination(s) · '+('round trip' if return_home else 'one way'))
    if stops and entry_mode != 'On the map':
        preview = go.Figure(go.Scatter(x=[lon]+[p['lon'] for p in stops]+([lon] if return_home else []),y=[lat]+[p['lat'] for p in stops]+([lat] if return_home else []),mode='lines+markers+text',text=['Origin']+[str(p['name']) for p in stops]+(['Return'] if return_home else []),textposition='top center',line=dict(color='#d47553',dash='dot')))
        preview.update_layout(height=250,margin=dict(l=20,r=20,t=25,b=20),xaxis_title='Longitude (°)',yaxis_title='Latitude (°)')
        st.plotly_chart(preview,width="stretch")
        st.caption('Visit order preview. Dotted lines are not terrain routes.')
    signature = json.dumps(dict(version=5,region=region,lon=lon,lat=lat,slope=slope,speed=speed,autonomy=autonomy,reserve=reserve,stops=stops,return_home=return_home,continuous_minutes=continuous_minutes,rest_minutes=rest_minutes),sort_keys=True,ensure_ascii=False)
    retry = False
    if stops and st.session_state.get('eva_error') and st.session_state.get('eva_attempt')==signature:
        retry = st.button('Retry calculation')
    if stops and (st.session_state.get('eva_attempt')!=signature or retry):
        st.session_state['eva_attempt'] = signature
        st.session_state.pop('eva_result',None)
        st.session_state.pop('eva_error',None)
        try:
            stops=json.loads(json.dumps(stops))
            for point in stops:
                point['lon']=float(point['lon'])
                if not -180<=point['lon']<180:
                    point['lon']=(point['lon']+180)%360-180
            bounds = bounds_for_points(lon,lat,stops)
            targets=[]
            for row in stops:
                x,y,t = float(row['lon']),float(row['lat']),float(row['minutes'])
                if not all(math.isfinite(v) for v in (x,y,t)) or t<0 or not row.get('name') or not str(row['name']).strip() or row.get('type','Science') not in ZONE_TYPES:
                    raise ValueError('Complete destination names, coordinates and durations.')
                targets.append(Waypoint(str(row['name']),x,y))
            scheduled_stops = json.loads(json.dumps(stops))
            if return_home:
                targets.append(Waypoint('Habitat · return',lon,lat))
                scheduled_stops.append(dict(name='Return to origin',type='Habitat',lon=lon,lat=lat,objective='Finish the traverse at the starting point. Record elapsed time and close out the mission log.',minutes=0.0))
            with st.spinner('Calculating your route…'):
                xs,ys,z = load_elevation(*bounds)
                route = plan_terrain_route(xs,ys,z,start_lon=lon,start_lat=lat,waypoints=targets,max_slope_percent=slope)
                if len(route.coordinates)<2:
                    raise ValueError('All destinations fall in the origin grid cell. Move them farther apart so MOLA can resolve the route.')
                waypoint_indices=[]; cursor=0
                for point in scheduled_stops:
                    snapped=(float(xs[np.argmin(abs(np.asarray(xs)-point['lon']))]),float(ys[np.argmin(abs(np.asarray(ys)-point['lat']))]))
                    cursor=route.coordinates.index(snapped,cursor)
                    waypoint_indices.append(cursor)
                heights=[float(z[np.argmin(abs(np.asarray(ys)-y)),np.argmin(abs(np.asarray(xs)-x))]) for x,y in route.coordinates]
                edge_distances=[math.hypot(distance_m(*a,*b),zb-za) for a,b,za,zb in zip(route.coordinates,route.coordinates[1:],heights,heights[1:])]
                schedule=schedule_route(route.coordinates,scheduled_stops,waypoint_indices,speed=speed,autonomy=autonomy,reserve=reserve,continuous_minutes=continuous_minutes,rest_minutes=rest_minutes,edge_distances=edge_distances)
                enrich_point_context(schedule,xs,ys,z)
            with st.spinner('Adding NASA and USGS resources…'):
                for index,event in enumerate(schedule['events'],1):
                    event['route_id']=str(index)
                resources=load_resources(bounds,[dict(name='Origin / habitat',lon=lon,lat=lat,route_id='H')]+schedule['events'],region,dict(lon=lon,lat=lat))
            st.session_state.eva_result=dict(xs=xs,ys=ys,z=z,bounds=bounds,route=route,lon=lon,lat=lat,stops=json.loads(json.dumps(stops)),events=schedule['events'],schedule=schedule,duration=schedule['duration_h'],usable=schedule['usable_h'],margin=schedule['margin_h'],signature=signature,region=region,resources=resources,return_home=return_home)
            st.rerun()
        except Exception as exc:
            st.session_state['eva_error']=str(exc)
    if not stops:
        st.session_state.pop('eva_result',None)
        st.session_state.pop('eva_attempt',None)
        st.session_state.pop('eva_error',None)
    if st.session_state.get('eva_error'):
        st.error('Could not update the route: '+st.session_state['eva_error'])
        st.caption('Check destinations and slope. If NASA is unavailable, use Retry.')
    result=st.session_state.get('eva_result')
    if not result:
        st.caption('Planning simulation · unverified zones.')
        return
    st.divider()
    r = result; route = r['route']
    a,b,c = st.columns(3)
    a.metric('Total distance',f'{route.distance_m/1000:.2f} km')
    b.metric('Total time',format_hours(r['duration']))
    c.metric('Remaining after reserve',format_hours(r['margin']))
    if r['margin'] < 0:
        st.error('Exceeds autonomy. Shorten the route or adjust the plan; resting does not recharge autonomy.')
    else:
        st.caption('Within the available time.')
    st.caption(f"{r['schedule']['rest_count']} rest stops · {r['schedule']['rest_minutes']:g} min resting")
    map_tab, profile_tab, science_tab, export_tab = st.tabs(['Itinerary','Elevation','Resources on route','Export'])
    with map_tab:
        render_point_inspector(r)
        with st.expander('Full mission schedule'):
            itinerary=[{'Point':p.get('route_id',str(i))+' · '+p['name'],'Purpose':point_objective(p),'Type':p.get('type','Science'),'Arrival':format_hours(p['arrival_min']/60),'On site (min)':p['minutes'],'km':round(p['distance_km'],2)} for i,p in enumerate(r['events'],1)]
            st.dataframe(itinerary,hide_index=True,width='stretch')
    with profile_tab:
        st.caption('MOLA elevation along your route')
        coords = route.coordinates
        distances = [0.0]
        heights = [r['z'][np.argmin(abs(np.asarray(r['ys'])-y)),np.argmin(abs(np.asarray(r['xs'])-x))] for x,y in coords]
        for p,q,za,zb in zip(coords,coords[1:],heights,heights[1:]):
            distances.append(distances[-1]+math.hypot(distance_m(*p,*q),zb-za)/1000)
        fig = go.Figure(go.Scatter(x=distances,y=heights,mode='lines',name='MOLA'))
        events=r['events']
        fig.add_trace(go.Scatter(x=[p['distance_km'] for p in events],y=np.interp([p['distance_km'] for p in events],distances,heights),mode='markers+text',text=[p.get('route_id',str(i)) for i,p in enumerate(events,1)],textposition='top center',customdata=[p['name'] for p in events],hovertemplate='%{text} · %{customdata}<br>%{x:.2f} km<br>%{y:.0f} m<extra></extra>',name='Zones',marker=dict(color=[ZONE_TYPES.get(p.get('type'),'#a356c9') for p in events],size=10)))
        fig.update_layout(xaxis_title='Distance along route (km)',yaxis_title='MOLA elevation (m)')
        st.plotly_chart(fig,width="stretch")
    with science_tab:
        render_route_resources(r,mars_map,zone_markers)
        with st.expander('Import a layer'):
            st.caption('CSV: lon,lat,value. Displayed alongside your route.')
            source = st.text_input('Mission, instrument and product URL',key='extra_layer_source')
            units = st.text_input('Variable and units (e.g. surface temperature, K)',key='extra_layer_units')
            uploaded = st.file_uploader('Scientific samples CSV',type=['csv'],key=f"extra_layer_file_{st.session_state.get('map_generation',0)}")
            if uploaded:
                try:
                    if not source.strip() or not units.strip():
                        raise ValueError('Provide a source and units for the samples.')
                    points = read_layer(uploaded.getvalue(),r['bounds'])
                    fig = go.Figure(go.Scatter(x=points[:,0],y=points[:,1],mode='markers',marker=dict(color=points[:,2],colorscale='Viridis',showscale=True,colorbar=dict(title=units)),text=points[:,2],hovertemplate='Lon %{x}<br>Lat %{y}<br>Value %{text}<extra></extra>'))
                    fig.add_trace(go.Scatter(x=[p[0] for p in coords],y=[p[1] for p in coords],mode='lines',name='Excursion',line=dict(color='red')))
                    fig.update_layout(xaxis_title='Longitude (°)',yaxis_title='Latitude (°)')
                    st.plotly_chart(fig,width="stretch")
                    st.caption(source)
                except (ValueError,KeyError,UnicodeError) as exc:
                    st.error(str(exc))
    with export_tab:
        mission = {'type':'FeatureCollection','properties':{'planet':'Mars','status':'simulation','duration_h':r['duration'],'usable_h':r['usable'],'margin_h':r['margin'],'science_stops':r['stops'],'terrain_source':route.source},'features':[{'type':'Feature','properties':{'name':'Planned excursion'},'geometry':{'type':'LineString','coordinates':coords}}]}
        mission['properties']['return_home'] = r['return_home']
        mission['properties']['rest_schedule'] = r['schedule']
        mission['properties']['resources'] = resource_manifest(r.get('resources',{}))
        if r.get('environment_scenario'):
            mission['properties']['historical_detector_scenario']=r['environment_scenario']
        if st.session_state.get('active_preset'):
            mission['properties']['preset']={key:st.session_state['active_preset'][key] for key in ('id','name','description','source')}
        mission['features'].extend({'type':'Feature','properties':dict(p,zone_status='proposed'),'geometry':{'type':'Point','coordinates':[p['lon'],p['lat']]}} for p in r['events'])
        mission['features'].append({'type':'Feature','properties':{'name':'Origin / habitat','type':'Habitat','zone_status':'proposed'},'geometry':{'type':'Point','coordinates':[r['lon'],r['lat']]}})
        st.download_button('Download mission (GeoJSON)',json.dumps(mission,ensure_ascii=False,indent=2,allow_nan=False),file_name='marswalk.geojson',mime='application/geo+json')
        if r.get('resources',{}).get('themis'):
            st.download_button('Download route-area THEMIS mosaic (PNG)',base64.b64decode(r['resources']['themis']['image'].split(',',1)[1]),file_name='marswalk_themis.png',mime='image/png')
    with st.expander('Sources and coverage'):
        st.caption('Simulation: route, rest stops and zones are not safety-validated.')
        st.write('Rest stops use the smaller of your continuous-walking setting and one quarter of autonomy after reserve. This is an adjustable planning assumption.')
        st.write('Elevation: MGS MOLA via NASA Mars Trek. Visible imagery: Viking MDIM 2.1. Infrared: historical Mars Odyssey THEMIS mosaic from USGS. Geology: Tanaka et al. (2014), regional scale 1:20 million. Photos: NASA Image and Video Library, regional context without verified positions along the route. Environment: dated REMS/MEDA outreach weather reports and quality-filtered RAD detector measurements where regionally associated. These are historical observations, not current forecasts. Autonomy and zones are planning assumptions. Worldview is an external Earth reference.')
        st.markdown('[NASA Mars Trek](https://trek.nasa.gov/mars/) · [THEMIS / Mars Odyssey instruments](https://science.nasa.gov/mission/odyssey/science-instruments/)')

    render_resources(region)
