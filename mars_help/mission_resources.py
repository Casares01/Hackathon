"""Public NASA/USGS resources attached to a mission, with explicit coverage."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
import json

import requests
from PIL import Image
from mars_help.environment import fetch_environment

WMS = 'https://planetarymaps.usgs.gov/cgi-bin/mapserv'
GEOLOGY = 'https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/Tanaka_et_al_2014_Mars_Global_Map_Features/FeatureServer/3/query'
MARS_GCS = 'GEOGCS["GCS_Mars_2000_Sphere",DATUM["D_Mars_2000_Sphere",SPHEROID["Mars_2000_Sphere",3396190.0,0.0]],PRIMEM["Reference_Meridian",0.0],UNIT["Degree",0.0174532925199433]]'
REGIONS = {'Jezero Crater':(77.39,18.45,'Jezero Perseverance'), 'Gale Crater':(137.44,-4.59,'Mount Sharp Curiosity'), 'Columbia Hills':(175.47,-14.58,'Columbia Hills Spirit'), 'Victoria Crater':(-5.50,-2.05,'Victoria Crater Opportunity'), 'Ares Vallis':(-33.22,19.13,'Ares Vallis Pathfinder')}


def themis_image(bounds):
    south,north,west,east = bounds
    response = requests.get(WMS,params={'map':'/maps/mars/mars_simp_cyl.map','SERVICE':'WMS','VERSION':'1.1.1','REQUEST':'GetMap','LAYERS':'THEMIS','STYLES':'','SRS':'EPSG:4326','BBOX':f'{west},{south},{east},{north}','WIDTH':1000,'HEIGHT':700,'FORMAT':'image/png'},timeout=25)
    response.raise_for_status()
    image = Image.open(BytesIO(response.content)); image.load()
    buffer = BytesIO();image.convert('RGB').save(buffer,format='PNG')
    return {'image':'data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode('ascii'),'bounds':list(bounds),'source':response.url,'label':'Mars Odyssey THEMIS · 100 m daytime infrared mosaic (v12, 2014)','coverage':'Historical infrared intensity mosaic; not current temperature or calibrated kelvin values.'}


def geology_at(point):
    spatial_ref = {'wkt':MARS_GCS}
    response = requests.get(GEOLOGY,params={'f':'json','geometry':json.dumps({'x':point['lon'],'y':point['lat'],'spatialReference':spatial_ref}),'geometryType':'esriGeometryPoint','inSR':json.dumps(spatial_ref),'spatialRel':'esriSpatialRelIntersects','outFields':'Unit,UnitDesc,Interpretation,UnitGroup','returnGeometry':'false'},timeout=25)
    response.raise_for_status(); payload = response.json()
    if payload.get('error'):
        raise ValueError(payload['error'].get('message','USGS service error'))
    return {'route_id':point.get('route_id'),'name':point['name'],'lon':point['lon'],'lat':point['lat'],'units':[item['attributes'] for item in payload.get('features',[])],'source':GEOLOGY,'scale':'1:20,000,000; regional context, not local hazard assessment'}


def regional_images(region, center):
    # Do not label remote region imagery as a photograph taken on this route.
    from mars_help.terrain_routes import distance_m
    ref = REGIONS.get(region)
    if not ref or distance_m(center['lon'],center['lat'],ref[0],ref[1]) > 100000:
        return {'items':[],'coverage':'The origin is outside the reference region; no regional photos are attached.'}
    response = requests.get('https://images-api.nasa.gov/search',params={'q':ref[2],'media_type':'image','page_size':3},timeout=25)
    response.raise_for_status(); items=[]
    for item in response.json().get('collection',{}).get('items',[]):
        data = (item.get('data') or [{}])[0]
        links = [link for link in item.get('links',[]) if link.get('render')=='image' and link.get('href','').startswith('https://')]
        if links:
            items.append({'id':data.get('nasa_id'),'title':data.get('title','NASA'),'date':data.get('date_created',''),'credit':data.get('secondary_creator',data.get('center','NASA')),'image':links[0]['href'],'description':data.get('description',''),'source':item.get('href','')})
    return {'items':items,'source':response.url,'coverage':'Regional context from NASA Image and Video Library; no verified match to individual route stops.'}


def fetch_resources(bounds, points, region, center):
    """Failures remain visible; a resource outage never discards a computed route."""
    bundle={'retrieved_at':datetime.now(timezone.utc).isoformat(),'geology':[],'errors':[]}
    jobs=[('themis',lambda:themis_image(bounds)),('images',lambda:regional_images(region,center)),('environment',lambda:fetch_environment(points))]
    jobs.extend(('geology',lambda p=p:geology_at(p)) for p in points)
    with ThreadPoolExecutor(max_workers=6) as pool:
        pending=[(name,pool.submit(function)) for name,function in jobs]
        for name,future in pending:
            try:
                value=future.result()
                if name=='geology': bundle[name].append(value)
                else: bundle[name]=value
            except (requests.RequestException,ValueError,KeyError,TypeError,OSError) as exc:
                bundle['errors'].append({'resource':name,'message':str(exc)})
    return bundle


def resource_manifest(bundle):
    """Keep provenance in exports without embedding raster base64 data."""
    return {key:({k:v for k,v in value.items() if k!='image'} if key=='themis' else value) for key,value in bundle.items()}


def geology_for_event(bundle,event):
    """Match actual coordinates, using stable route IDs to disambiguate revisits."""
    matches=[point for point in bundle.get('geology',[]) if abs(point['lon']-event['lon'])<1e-7 and abs(point['lat']-event['lat'])<1e-7]
    return next((point for point in matches if point.get('route_id')==event.get('route_id')),matches[0] if matches else None)
