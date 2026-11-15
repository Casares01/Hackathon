"""Compact resource views that share the route's coordinates and stop labels."""
import streamlit as st
from mars_help.mission_resources import geology_for_event
from mars_help.point_details import point_objective
from mars_help.environment_views import render_environment


def render_point_inspector(result):
    events=result['events']
    selected=st.selectbox('Inspect a point',range(len(events)),index=None,placeholder='Choose a mission point',format_func=lambda i:f"{events[i].get('route_id',i+1)} · {events[i]['name']}",key='inspect_point')
    if selected is None:
        st.caption('Click a map marker for its activity, or select a point for terrain and timing details.')
        return
    point=events[selected]
    with st.container(border=True):
        task,data=st.columns([2,1])
        with task:
            st.subheader(point['name'])
            st.caption(('Automatic rest stop' if point.get('automatic') else 'Planned '+point.get('type','science').lower()+' activity')+f" · route point {point.get('route_id',selected+1)}")
            st.write(point_objective(point))
            st.caption(f"Route position · {point['lat']:.5f}° latitude · {point['lon']:.5f}° longitude")
            offset=point.get('grid_offset_m',0)
            if offset>.5:
                st.caption(f"Requested target is {offset:.0f} m from this routing-grid position.")
        with data:
            st.write(f"**Arrival** · {point['arrival_min']:.0f} min after departure")
            st.write(f"**On site** · {point['minutes']:g} min")
            st.write(f"**Along route** · {point['distance_km']:.2f} km")
            elevation=point.get('elevation_m')
            st.write(f"**MOLA elevation** · {elevation:,.0f} m" if elevation is not None else '**MOLA elevation** · unavailable')
            geology=geology_for_event(result.get('resources',{}),point)
            if geology and geology.get('units'):
                st.write('**USGS unit** · '+', '.join(unit.get('Unit','') for unit in geology['units']))


def render_route_resources(result,map_component,markers):
    r=result
    bundle=r.get('resources',{})
    mode=st.radio('Resource',['Infrared · THEMIS','Geology · USGS','Weather & radiation','Regional photos'],horizontal=True,label_visibility='collapsed')
    points=markers(r['events'],r['lon'],r['lat'])
    kwargs=dict(center={'lon':r['lon'],'lat':r['lat']},points=points,route=r['route'].coordinates,zoom=11,readonly=True,default=None)
    if mode=='Infrared · THEMIS':
        themis=bundle.get('themis')
        if themis:
            kwargs['raster']={'image':themis['image'],'bounds':themis.get('bounds',r['bounds'])}
        map_component(**kwargs,key='resource_themis',caption='THEMIS infrared coverage · red route · numbered zones')
        if themis:
            st.caption('Historical infrared mosaic · 100 m/pixel · not current temperature')
            with st.expander('Source and coverage'):
                st.write(themis['label'])
                st.write(themis['coverage'])
                st.write(dict(zip(['South','North','West','East'],themis.get('bounds',r['bounds']))))
                st.link_button('USGS product',themis['source'])
        else:
            st.info('THEMIS is unavailable. Your route is shown over Viking imagery.')
    elif mode=='Geology · USGS':
        events=[{'name':'Origin / habitat','lon':r['lon'],'lat':r['lat'],'route_id':'H'}]+r['events']
        selected=st.selectbox('Route stop',range(len(events)),format_func=lambda i:f"{events[i].get('route_id',i)} · {events[i]['name']}"+ (f" · {events[i]['distance_km']:.2f} km" if 'distance_km' in events[i] else ''))
        event=events[selected]
        point=geology_for_event(bundle,event)
        for marker,ref in zip(points,events):
            data=geology_for_event(bundle,ref)
            marker['detail']=' · '.join(unit.get('Unit','') for unit in data.get('units',[])) if data else 'No geological data'
        kwargs['focus']={'lat':event['lat'],'lon':event['lon'],'name':f"{event.get('route_id',selected)} · {event['name']}"}
        left,right=st.columns([2,1])
        with left:
            map_component(**kwargs,key='resource_geology',caption='Highlighted stop: USGS geology queried at its coordinates')
        with right:
            st.markdown(f"**{event.get('route_id',selected)} · {event['name']}**")
            st.caption(f"{event['lat']:.5f}° · {event['lon']:.5f}°")
            if point and point.get('units'):
                for unit in point['units']:
                    st.metric('Geological unit',unit.get('Unit','—'))
                    st.write(unit.get('UnitDesc',''))
                    with st.expander('Interpretation and source'):
                        st.write(unit.get('Interpretation',''))
                        st.caption(point['scale'])
                        st.link_button('USGS query',point['source'])
            else:
                st.info('No geological unit is available for this stop.')
            st.caption('Regional geology · 1:20 million scale')
    elif mode=='Weather & radiation':
        render_environment(r,map_component,markers)
    else:
        map_component(**kwargs,key='resource_photos',caption='Photos describe the origin region; their positions on this route are unverified')
        st.caption(f"Context for {r['region']} · not verified photos of individual stops")
        photos=bundle.get('images',{})
        items=photos.get('items',[])
        if not items:
            st.info('No regional photos are available for this origin.')
        else:
            for column,photo in zip(st.columns(len(items)),items):
                with column:
                    st.image(photo['image'],caption=photo['title'])
                    with st.expander('Date, description and source'):
                        st.caption(photo['credit']+' · '+photo['date'])
                        st.write(photo['description'])
                        st.link_button('NASA',photo['source'])
    if bundle.get('errors'):
        with st.expander('Unavailable sources'):
            for error in bundle['errors']:
                st.write(error['resource']+': '+error['message'])
