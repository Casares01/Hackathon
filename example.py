"""Marswalk: Mars itineraries and route-linked science resources."""
import streamlit as st
from mars_help.mars_elevation import MarsElevationAPI
from mars_help.marswalk import render
from mars_help.presets import LOCATIONS

st.set_page_config(page_title='Marswalk - Explore Mars',page_icon='🪐',layout='wide')

@st.cache_data(ttl=3600,show_spinner=False)
def load_elevation_bbox(min_lat,max_lat,min_lon,max_lon):
    return MarsElevationAPI().get_elevation_grid(min_lat=min_lat,max_lat=max_lat,min_lon=min_lon,max_lon=max_lon,rows=22,columns=85)

def main():
    render(load_elevation_bbox,LOCATIONS)

if __name__=='__main__':
    main()
