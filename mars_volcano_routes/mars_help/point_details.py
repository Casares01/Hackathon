"""Task descriptions and measured context for itinerary points."""
import numpy as np


ZONE_OBJECTIVES={
    'Science':'Take context photographs, compare visible surface textures, and record observations with their coordinates.',
    'Rest':'Pause and review elapsed time, remaining autonomy and the next walking segment.',
    'Landing':'Document surrounding relief and surface texture for a proposed landing-area assessment.',
    'Habitat':'Review the planned base location and return logistics. This waypoint does not replenish autonomy.',
    'Communications':'Log the outcome of a planned communications check and note any terrain blocking the line of sight.',
}


def point_objective(point):
    value=point.get('objective')
    if isinstance(value,str) and value.strip():
        return value.strip()
    return ZONE_OBJECTIVES.get(point.get('type','Science'),ZONE_OBJECTIVES['Science'])


def enrich_point_context(schedule,xs,ys,grid):
    """Preserve requested positions; report the actual routing-grid displacement."""
    from mars_help.terrain_routes import distance_m
    for point in schedule['events']:
        i=int(np.argmin(abs(np.asarray(ys)-point['lat'])))
        j=int(np.argmin(abs(np.asarray(xs)-point['lon'])))
        point['elevation_m']=float(grid[i,j]) if np.isfinite(grid[i,j]) else None
        point['objective']=point_objective(point)
        if not point.get('automatic'):
            point['grid_offset_m']=distance_m(point.get('requested_lon',point['lon']),point.get('requested_lat',point['lat']),point['lon'],point['lat'])
    return schedule
