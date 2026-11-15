"""Historical NASA weather and quality-filtered RAD data with spatial scope."""
from datetime import date,datetime,timedelta,timezone
import math
import re
from statistics import median

import requests

from mars_help.terrain_routes import distance_m

WEATHER_API='https://mars.nasa.gov/rss/api/'
RAD_ARCHIVE='https://spdf.gsfc.nasa.gov/pub/data/aaa_planetary/msl/rad/cdf/obs-l2/'
RAD_DATA='https://cdaweb.gsfc.nasa.gov/WS/cdasr/1/dataviews/sp_phys/datasets/MSL_RAD_OBS-L2/data/'
STATIONS={
    'msl':dict(name='Curiosity / REMS',region='Gale Crater',lon=137.44,lat=-4.59,association_km=75,
               source='https://science.nasa.gov/mission/msl-curiosity/science-instruments/'),
    'mars2020':dict(name='Perseverance / MEDA',region='Jezero Crater',lon=77.39,lat=18.45,association_km=25,
                    source='https://science.nasa.gov/mission/mars-2020-perseverance/science-instruments/'),
}


def finite_number(value):
    try:
        number=float(value)
    except (TypeError,ValueError):
        return None
    return number if math.isfinite(number) else None


def weather_records(payload,as_of=None):
    """Keep same-sol readings together; never substitute zero for missing values."""
    today=as_of or datetime.now(timezone.utc).date()
    rows=payload.get('soles',payload.get('sols',[]))
    if not isinstance(rows,list):
        raise ValueError('Unexpected NASA weather feed format.')
    records=[]
    keys={'min_temp':'air_min_c','max_temp':'air_max_c','min_gts_temp':'ground_min_c',
          'max_gts_temp':'ground_max_c','pressure':'pressure_pa','wind_speed':'wind_ms'}
    for row in rows:
        try:
            measured=date.fromisoformat(str(row.get('terrestrial_date',''))[:10])
        except ValueError:
            continue
        if measured>today:
            continue
        record=dict(date=measured.isoformat(),sol=str(row.get('sol','')))
        for source,target in keys.items():
            value=finite_number(row.get(source))
            record[target]=None if value is not None and target in ('pressure_pa','wind_ms') and value<0 else value
        for low,high in [('air_min_c','air_max_c'),('ground_min_c','ground_max_c')]:
            if record[low] is not None and record[high] is not None and record[low]>record[high]:
                record[low]=record[high]=None
        uv=str(row.get('local_uv_irradiance_index','')).strip()
        record['uv_category']=uv if uv.lower() not in ('','--','none','n/a','null') else None
        if any(record[key] is not None for key in keys.values()) or record['uv_category'] is not None:
            records.append(record)
    return sorted(records,key=lambda row:(row['date'],row['sol']))[-14:]


def fetch_weather(category):
    response=requests.get(WEATHER_API,params=dict(feed='weather',category=category,feedtype='json'),timeout=20)
    response.raise_for_status();payload=response.json()
    records=weather_records(payload)
    if not records:
        raise ValueError('No dated weather measurements are available in this feed.')
    return dict(instrument=STATIONS[category]['name'],station=STATIONS[category],source=response.url,
                historical=True,records=records,latest=records[-1],
                use='Outreach daily reports, not operational weather or a forecast.',
                provider_disclaimer=(payload.get('descriptions') or {}).get('disclaimer_en','').strip())


def _variables(payload):
    products=[]
    for product in payload.values():
        if not isinstance(product,dict) or 'CDFVariables' not in product:
            continue
        variables={}
        for entry in product['CDFVariables']:
            for name,parts in entry.items():
                variable={}
                for part in parts:
                    variable.update(part)
                variable['attributes']={key:value for item in variable.get('VarAttributes',[]) for key,value in item.items()}
                variables[name]=variable
        products.append(variables)
    return products


def radiation_records(payload,as_of=None):
    """Read detector E by its metadata label, not by an assumed column number."""
    today=as_of or datetime.now(timezone.utc).date()
    records=[]
    for variables in _variables(payload):
        dose=variables.get('DOSIMETRY_TOTAL_f')
        if not dose:
            continue
        attrs=dose['attributes']
        if not str(attrs.get('UNITS','')).lower().startswith('ugray/day'):
            raise ValueError('Unrecognised RAD dose-rate units; no conversion was applied.')
        labels=variables.get(attrs.get('LABL_PTR_1'),{}).get('VarData',[])
        channel=next((index for index,label in enumerate(labels) if str(label).strip()=='Total Dose E'),None)
        if channel is None:
            raise ValueError('RAD detector E could not be identified in the metadata.')
        times=variables.get(attrs.get('DEPEND_0','EPOCH'),{}).get('VarData',[])
        values=dose.get('VarData',[])
        flags=variables.get('FLAGGED_DATA',{}).get('VarData')
        low,high=attrs.get('VALIDMIN',0),attrs.get('VALIDMAX',math.inf)
        fill=attrs.get('FILLVAL')
        for index,(stamp,row) in enumerate(zip(times,values)):
            try:
                measured=date.fromisoformat(str(stamp)[:10])
                value=finite_number(row[channel])
            except (ValueError,TypeError,IndexError):
                continue
            if measured<date(2012,8,6) or measured>today or value is None or value==fill or value<0 or not low<=value<=high:
                continue
            if flags is not None and (index>=len(flags) or str(flags[index]).strip()):
                continue
            records.append(dict(time=str(stamp),dose_rate_ugy_day=value))
    return sorted(records,key=lambda row:row['time'])


def fetch_radiation(as_of=None):
    today=as_of or datetime.now(timezone.utc).date()
    available=[]
    for year in (today.year,today.year-1):
        response=requests.get(RAD_ARCHIVE+f'{year}/',timeout=20)
        response.raise_for_status()
        for code in set(re.findall(r'msl_rad_obs-l2_(\d{7})_v\d+\.cdf',response.text)):
            measured=datetime.strptime(code,'%Y%j').date()
            if date(2012,8,6)<=measured<=today:
                available.append(measured)
        if available:
            break
    if not available:
        raise ValueError('No dated surface RAD files were found in the archive.')
    for measured in sorted(set(available),reverse=True)[:3]:
        end=measured+timedelta(days=1)
        url=RAD_DATA+measured.strftime('%Y%m%dT000000Z')+','+end.strftime('%Y%m%dT000000Z')+'/DOSIMETRY_TOTAL_f,ALIVE_TIME_f'
        response=requests.get(url,params={'format':'cdfjson'},timeout=25)
        response.raise_for_status()
        records=radiation_records(response.json(),today)
        if records:
            values=[record['dose_rate_ugy_day'] for record in records]
            return dict(instrument='Curiosity / RAD',historical=True,date=measured.isoformat(),
                        station=STATIONS['msl'],source=response.url,archive=RAD_ARCHIVE,
                        channel='Detector E · tissue-equivalent plastic',unit='µGy/day',quality='DOSIMETRY_TOTAL_f; flagged and fill values excluded',credit='RAD: D. Hassler / SwRI; archive: NASA SPDF / CDAWeb',
                        records=records,median_ugy_day=median(values),minimum_ugy_day=min(values),maximum_ugy_day=max(values),
                        use='Absorbed dose in the detector, not human effective dose or a suit-shielding model.')
    raise ValueError('No quality-filtered RAD observations were available in the latest archived days.')


def associated_points(points,station):
    # This is an approximate regional association, not a sensor coverage radius.
    return [str(point.get('route_id',index)) for index,point in enumerate(points) if distance_m(point['lon'],point['lat'],station['lon'],station['lat'])<=station['association_km']*1000]


def fetch_environment(points):
    from concurrent.futures import ThreadPoolExecutor
    result={'weather':[],'radiation':None,'errors':[],
            'coverage_note':'Rover measurements are regional references, not point-by-point conditions along this route.'}
    jobs=[]
    for category,station in STATIONS.items():
        ids=associated_points(points,station)
        if ids:
            jobs.append(('weather',ids,lambda category=category:fetch_weather(category)))
            if category=='msl':
                jobs.append(('radiation',ids,fetch_radiation))
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending=[(kind,ids,pool.submit(function)) for kind,ids,function in jobs]
        for kind,ids,future in pending:
            try:
                resource=future.result()
                resource['route_point_ids']=ids
                resource['whole_itinerary_associated']=len(ids)==len(points)
                if kind=='weather':
                    result[kind].append(resource)
                else:
                    result[kind]=resource
            except (requests.RequestException,ValueError,KeyError,TypeError) as exc:
                result['errors'].append(dict(resource=kind,message=str(exc)))
    return result


def radiation_scenario(resource,duration_h):
    """Explicit historical constant-rate detector scenario, never a forecast."""
    if not resource or not resource.get('whole_itinerary_associated'):
        return None
    duration=finite_number(duration_h)
    rate=finite_number(resource.get('median_ugy_day'))
    if duration is None or duration<0 or rate is None or rate<0:
        raise ValueError('Invalid detector-dose scenario values.')
    return dict(absorbed_detector_dose_ugy=rate*duration/24,duration_h=duration,
                reference_date=resource['date'],rate_ugy_day=rate,unit='µGy',
                assumption='Historical detector E median held constant for the complete route duration, including rests. Not a forecast or personal dose estimate.')
