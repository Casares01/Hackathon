# """Mapa topográfico de Marte: NASA Mars Trek WMTS + modelo MOLA de elevaciones."""
# from pathlib import Path
# import math
# from io import BytesIO

# import matplotlib.pyplot as plt
# import numpy as np
# import requests
# import rasterio
# from PIL import Image
# from rasterio.windows import Window
import streamlit as st


st.title("Mars Survival Map")
st.text("Choose a Destination:")


import requests

API_URL = "https://oderest.rsl.wustl.edu/live2"


def search_hrsc(lat, lon, radius=0.5):
    """
    Search for HRSC observations around
    a location on Mars.

    lat: latitude
    lon: longitude (0–360)
    radius: search radius in degrees
    """

    params = {
        "target": "mars",
        "query": "products",
        "results": "fmpc",
        "output": "JSON",

        # Mars Express spacecraft
        "ihid": "MEX",

        # HRSC camera
        "iid": "HRSC",

        # Geographic area
        "minlat": lat - radius,
        "maxlat": lat + radius,
        "westernlon": lon - radius,
        "easternlon": lon + radius,
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=60
    )

    response.raise_for_status()

    return response.json()


# Search near Jezero Crater
data = search_hrsc(
    lat=18.38,
    lon=77.58
)

print(data)