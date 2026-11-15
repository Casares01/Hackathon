"""Geometry and explicit time-budget rules for automatic mission planning."""
import math

from mars_help.terrain_routes import distance_m


def bounds_for_points(lon, lat, stops):
    points = [(lon,lat)]+[(float(p['lon']),float(p['lat'])) for p in stops]
    if not all(math.isfinite(x) and math.isfinite(y) and -180<=x<180 and -90<=y<=90 for x,y in points):
        raise ValueError('Check the point coordinates.')
    xs,ys=zip(*points)
    if max(xs)-min(xs)>180:
        raise ValueError('This route crosses the antimeridian, which the download service does not yet support.')
    # Padding serves raster sampling only; it never limits point placement.
    dx=max(.005,(max(xs)-min(xs))*.05)
    dy=max(.005,(max(ys)-min(ys))*.05)
    return max(-90,min(ys)-dy),min(90,max(ys)+dy),max(-180,min(xs)-dx),min(180,max(xs)+dx)


def schedule_route(coordinates, stops, waypoint_indices, *, speed, autonomy, reserve,
                   continuous_minutes=60, rest_minutes=10, edge_distances=None,travel_mode='Walking'):
    """Place time-based rest proposals on the computed path, including its return.

    Rest cadence is a planning assumption, not a physiological model. The walking
    block is at most one quarter of usable autonomy and the user-selected cap.
    Rest consumes the same total time budget and never replenishes autonomy.
    """
    values=(speed,autonomy,reserve,continuous_minutes,rest_minutes)
    if travel_mode not in ('Walking','Rover'):
        raise ValueError('Unknown travel mode.')
    if not all(math.isfinite(v) for v in values) or speed<=0 or autonomy<=0 or not 0<=reserve<100 or continuous_minutes<=0 or rest_minutes<=0:
        raise ValueError('Check speed, autonomy and rest durations.')
    if len(stops)!=len(waypoint_indices) or waypoint_indices!=sorted(waypoint_indices) or any(i<0 or i>=len(coordinates) for i in waypoint_indices):
        raise ValueError('Waypoints must follow route order.')
    usable_minutes=autonomy*60*(1-reserve/100)
    interval=min(continuous_minutes,usable_minutes/4)
    meters_per_minute=speed*1000/60
    lengths=list(edge_distances) if edge_distances is not None else [distance_m(*a,*b) for a,b in zip(coordinates,coordinates[1:])]
    if len(lengths)!=max(0,len(coordinates)-1) or any(not math.isfinite(d) or d<0 for d in lengths):
        raise ValueError('Invalid route distances.')
    by_index={}
    for stop,index in zip(stops,waypoint_indices):
        minutes=float(stop['minutes'])
        if not math.isfinite(minutes) or minutes<0:
            raise ValueError('Invalid stop duration.')
        by_index.setdefault(index,[]).append(stop)
    events=[]; elapsed=0.; walking_since_rest=0.; travelled=0.; rest_count=0

    def visit(index):
        nonlocal elapsed,walking_since_rest
        for stop in by_index.get(index,[]):
            event=dict(stop,requested_lon=stop.get('lon',coordinates[index][0]),requested_lat=stop.get('lat',coordinates[index][1]),lon=float(coordinates[index][0]),lat=float(coordinates[index][1]),automatic=False,arrival_min=elapsed,distance_km=travelled/1000)
            events.append(event)
            elapsed+=float(stop['minutes'])
            if stop.get('type')=='Rest' and float(stop['minutes'])>=rest_minutes:
                walking_since_rest=0.

    visit(0)
    for index,(a,b,length) in enumerate(zip(coordinates,coordinates[1:],lengths),1):
        used=0.
        while used<length-1e-8:
            if walking_since_rest>=interval-1e-8:
                fraction=used/length
                rest_count+=1
                activity='driving' if travel_mode=='Rover' else 'walking'
                events.append({'name':f'Rest {rest_count}','type':'Rest','lon':a[0]+(b[0]-a[0])*fraction,'lat':a[1]+(b[1]-a[1])*fraction,'objective':f'Take a {rest_minutes:g}-minute break after {interval:g} minutes of {activity}. Review remaining autonomy before the next segment.','minutes':float(rest_minutes),'automatic':True,'arrival_min':elapsed,'distance_km':travelled/1000})
                elapsed+=rest_minutes;walking_since_rest=0.
            step=min(length-used,(interval-walking_since_rest)*meters_per_minute)
            used+=step;travelled+=step
            elapsed+=step/meters_per_minute;walking_since_rest+=step/meters_per_minute
        visit(index)
    return {'events':events,'rest_count':rest_count,'rest_minutes':rest_count*rest_minutes,
            'walk_minutes':sum(lengths)/meters_per_minute,'duration_h':elapsed/60,
            'usable_h':usable_minutes/60,'margin_h':(usable_minutes-elapsed)/60,
            'walking_block_minutes':interval,'rest_duration_minutes':rest_minutes,'travel_mode':travel_mode}
