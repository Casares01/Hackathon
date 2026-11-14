"""Route-linked historical conditions, kept distinct from current hazards."""
import plotly.graph_objects as go
import streamlit as st

from mars_help.environment import radiation_scenario


def _value(value,unit='',decimals=1):
    return 'Not reported' if value is None else f'{value:,.{decimals}f} {unit}'.strip()


def _temperature(record,low,high):
    if record.get(low) is None or record.get(high) is None:
        return 'Not reported'
    return f"{record[low]:g} to {record[high]:g} °C"


def render_environment(result,map_component,markers):
    bundle=result.get('resources',{}).get('environment',{})
    st.caption('Historical rover observations · not a mission-day forecast')
    map_component(center={'lon':result['lon'],'lat':result['lat']},points=markers(result['events'],result['lon'],result['lat']),
                  route=result['route'].coordinates,readonly=True,key='resource_environment',default=None,
                  caption='Regional references only: weather and radiation are not measured point by point along the red route.')
    weather=bundle.get('weather',[])
    if weather:
        index=0
        if len(weather)>1:
            index=st.selectbox('Weather reference',range(len(weather)),format_func=lambda i:weather[i]['instrument'])
        report=weather[index];latest=report['latest']
        st.subheader(report['instrument'])
        st.caption(f"{report['station']['region']} · {latest['date']} · sol {latest['sol']} · most recent report with measurements in this feed")
        air,pressure,uv=st.columns(3)
        air.metric('Air temperature',_temperature(latest,'air_min_c','air_max_c'))
        pressure.metric('Pressure',_value(latest.get('pressure_pa'),'Pa'))
        uv.metric('Local UV category',latest.get('uv_category') or 'Not reported')
        st.caption('Associated route points: '+', '.join(report.get('route_point_ids',[]))+'. Regional association does not establish conditions at these positions.')
        with st.expander('Daily history and measurement details'):
            rows=report['records']
            fig=go.Figure()
            for name,key in [('Daily minimum','air_min_c'),('Daily maximum','air_max_c')]:
                fig.add_trace(go.Scatter(x=[row['date'] for row in rows],y=[row.get(key) for row in rows],name=name,mode='lines+markers',connectgaps=False))
            fig.update_layout(height=280,yaxis_title='Reported air temperature (°C)',xaxis_title='Measurement date')
            st.plotly_chart(fig,width='stretch')
            ground,wind=st.columns(2)
            ground.metric('Ground temperature',_temperature(latest,'ground_min_c','ground_max_c'))
            wind.metric('Wind speed',_value(latest.get('wind_ms'),'m/s'))
            st.caption(report['use'])
            st.write('Instrument reference position is regional; the feed does not provide the rover location for each report.')
            st.link_button('NASA weather feed',report['source'])
            st.link_button('Instrument information',report['station']['source'])
            if report.get('provider_disclaimer'):
                st.write(report['provider_disclaimer'])
    else:
        st.info('No route-associated weather report is available. The connected feeds measure the Jezero and Gale regions.')
    st.divider()
    radiation=bundle.get('radiation')
    if radiation:
        st.subheader('Ionizing radiation · Curiosity / RAD')
        st.caption(f"Gale Crater reference · archive day {radiation['date']} · {radiation['channel']}")
        rate,count=st.columns(2)
        rate.metric('Median observed absorbed-dose rate',f"{radiation['median_ugy_day']:.2f} µGy/day")
        count.metric('Quality-filtered observations',str(len(radiation['records'])))
        st.caption('Detector measurements, not human effective dose. UV categories above describe a different measurement.')
        if radiation.get('whole_itinerary_associated'):
            if st.checkbox('Compare with the complete route duration',key='radiation_duration_scenario'):
                scenario=radiation_scenario(radiation,result['duration'])
                result['environment_scenario']=scenario
                st.metric('Same-duration detector-dose scenario',f"{scenario['absorbed_detector_dose_ugy']:.2f} µGy")
                st.caption(f"For your {result['duration']:.2f} h plan, including activities and rests. Historical median × hours / 24; not a forecast, suit-shielding model or personal dose estimate.")
            else:
                result.pop('environment_scenario',None)
        else:
            st.caption('Radiation reference matches only some route points; no whole-route dose comparison is applied.')
        with st.expander('Radiation time series, quality and source'):
            rows=radiation['records']
            fig=go.Figure(go.Scatter(x=[row['time'] for row in rows],y=[row['dose_rate_ugy_day'] for row in rows],mode='lines+markers',name='RAD detector E'))
            fig.update_layout(height=280,xaxis_title='Observation time (UTC)',yaxis_title='Absorbed dose rate (µGy/day)')
            st.plotly_chart(fig,width='stretch')
            st.caption(radiation['quality'])
            if radiation.get('credit'):
                st.caption(radiation['credit'])
            st.caption('Associated route points: '+', '.join(radiation.get('route_point_ids',[])))
            st.write(radiation['use'])
            st.link_button('NASA CDAWeb measurement data',radiation['source'])
            st.link_button('NASA RAD archive',radiation['archive'])
    else:
        result.pop('environment_scenario',None)
        st.info('No route-associated ionizing-radiation measurement is available. RAD is a Gale Crater instrument, not a global radiation map.')
        st.link_button('NASA radiation measurement background','https://science.nasa.gov/resource/radiation-measurements-on-mars/')
    if bundle.get('errors'):
        with st.expander('Unavailable environment sources'):
            for error in bundle['errors']:
                st.write(error['resource']+': '+error['message'])
