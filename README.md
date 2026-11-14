# Marswalk

An English-language Mars itinerary planner with editable destinations, automatic
rest stops and NASA/USGS resources linked to the route.

## Run

On this computer:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

The launcher uses the isolated Python in `.runtime`. On another computer:

```sh
pip install -r requirements.txt
python -m streamlit run example.py
```

## Plan a route

Choose one of five prepared itineraries, or keep **Custom route** and click the
map to add destinations. Set an origin, zone types and activity durations.
Routes and rest stops update automatically as destinations or settings change.
Use **Clear route** to remove the draft, calculated route, rest stops, imported
layer and selected map point. Your origin and numerical settings are preserved.
Coordinate and distance entry also start empty after clearing.

Mission controls are grouped in the sidebar. The main workspace provides
**Topography** and **Satellite** views of the same route. Before calculation,
the topographic basemap uses global USGS/NASA MOLA relief. After calculation,
the map overlays the route's MOLA grid with elevation colours, labelled contour
lines and a metre-based legend. Sparse sampling remains sparse information;
the rendered surface does not resolve additional ground hazards.

Click a numbered marker to read its planned activity. **Inspect a point** in
the itinerary shows its objective, arrival time, duration, elevation and USGS
unit when available. It also reports the distance between a requested target
and the DEM cell used for routing. The full schedule and export preserve these
descriptions and requested coordinates. Automatic rests explain the configured
walking interval that triggered them.

There is no exploration radius or arbitrary numeric input cap. Invalid values
are reported after entry: coordinates must be geographically valid, walking
speed and durations must permit calculation, and reserve must be below 100%.

## Five prepared itineraries

Each is an editable proposal with three science stops, a suggested origin and
initial settings. The path is calculated using NASA MOLA when selected; it is
not a copied rover track or a verified safe astronaut traverse. Stop names are
proposed observation tasks, not claims of discoveries at exact coordinates.

| Route | Exploration theme | NASA background |
| --- | --- | --- |
| Jezero · Ancient Delta | An ancient river-delta landscape | [Jezero delta](https://science.nasa.gov/resource/perseverance-explores-the-jezero-crater-delta/) |
| Gale · Layers of Time | Sedimentary history around Mount Sharp | [Mount Sharp](https://science.nasa.gov/resource/the-making-of-mount-sharp/) |
| Columbia Hills · Water Clues | The terrain explored by Spirit | [Spirit](https://science.nasa.gov/mission/mer-spirit/) |
| Victoria · Crater Stories | The impact landscape visited by Opportunity | [Victoria Crater](https://science.nasa.gov/photojournal/victoria-crater-at-meridiani-planum/) |
| Ares Vallis · Floodplain Explorer | The Pathfinder-region floodplain | [Mars Pathfinder](https://science.nasa.gov/mission/mars-pathfinder/) |

## Rest stops and autonomy

The walking interval is the smaller of the continuous-walking setting and one
quarter of autonomy after reserve. Defaults are 60 minutes walking and 10
minutes per rest. Manual rest stops of sufficient duration reset the walking
counter. Return travel receives rest stops too when enabled.

All walking, activities and rests consume the total time budget. Resting does
not replenish autonomy. The app flags routes that exceed the available budget.
This cadence is an adjustable planning assumption, not a physiological model.

## Resources on route

- **MGS MOLA:** route planning and an elevation profile with matching zone IDs.
- **Viking MDIM 2.1:** NASA Mars Trek visible map imagery.
- **Mars Odyssey THEMIS:** a historical daytime infrared mosaic from USGS,
  placed in its geographic footprint with the route and numbered zones over it.
  It is infrared intensity, not current temperature or calibrated kelvin values.
- **USGS geology:** Tanaka et al. (2014), scale 1:20 million, queried at the
  origin and itinerary zones. Select a numbered stop to highlight its location
  and view the associated geological unit.
- **NASA regional photos:** images with title, date and provenance from NASA
  Image and Video Library. They describe the origin region, without verified
  positions on individual route stops. Photos are not attached when the origin
  is farther than 100 km from the selected reference region.

Resources are cached for one hour. An unavailable source is reported without
discarding the route. A UTF-8 CSV with `lon,lat,value` can add another variable;
source and units are required. Uploaded samples do not influence pathfinding.
Worldview is an external Earth-map reference and is not used as Mars data.

The GeoJSON export includes the route, typed zones, automatic rests, arrival
times, geological associations, resource provenance and preset metadata when
applicable. The THEMIS area mosaic is also downloadable as PNG.

## Weather and radiation

**Resources on route → Weather & radiation** attaches NASA measurements when
the itinerary has points regionally associated with a supported rover:

- **Gale:** Curiosity REMS daily weather, including air/ground temperature,
  pressure, wind and the local UV category when the feed reports them.
- **Jezero:** Perseverance MEDA daily weather where values are published.
- **Gale radiation:** quality-filtered Curiosity RAD Level-2 detector-E dose
  rates from NASA SPDF/CDAWeb, identified using channel metadata. Fill values,
  out-of-range samples and flagged observations are excluded.

Dates, source links and associated route-point IDs are shown and exported.
Missing measurements remain missing. A report is selected from a single sol;
values are not borrowed from another day to fill gaps. Weather reports are
outreach products, not operational measurements or forecasts. Measurement
sites move with the rovers; the feeds do not provide a position per report.
Regional reference positions are not displayed as precise sensor locations.

An optional comparison holds the historical detector-E median constant over
the full route duration, including rests. It reports absorbed detector dose
in micrograys, not human effective dose or dose inside a spacesuit. It is
offered only when all itinerary points are regionally associated with Gale.
UV categories and RAD ionizing-radiation data remain separate measurements.

Historical observations do not change pathfinding, walking speed, rest rules,
or the app's assessment of route safety. Routes elsewhere show that no
route-associated observations are available rather than applying Gale data
to the whole planet. Provider outages are reported independently.

Sources: [NASA Mars weather feed](https://mars.nasa.gov/rss/api/?feed=weather&category=msl&feedtype=json),
[Perseverance instrument information](https://science.nasa.gov/mission/mars-2020-perseverance/science-instruments/),
[RAD Level-2 archive](https://spdf.gsfc.nasa.gov/pub/data/aaa_planetary/msl/rad/cdf/obs-l2/),
[NASA CDAWeb service documentation](https://cdaweb.gsfc.nasa.gov/WebServices/REST/).

## Scope

Educational planning simulation. MOLA cannot resolve small rocks, cracks or
sand hazards. Proposed landing, rest and habitat zones are not validated sites.
Waypoints snap to DEM cells. Routes crossing the antimeridian are not supported.
Internet is needed for basemaps, NASA elevation and external resource services.
The former volcano-routing mode has been removed; its terrain solver is now a
generic waypoint planner in `mars_help/terrain_routes.py`. Original source
data and the NASA elevation helper are retained.

## Tests

```sh
python -m unittest discover -s tests -v
```

On this computer use `.runtime\python.exe` for the commands above.
