"""Display-only elevation sampling driven by the visible map, not route bounds."""
import math
import numpy as np


def view_bounds(raw):
    if not isinstance(raw,(list,tuple)) or len(raw)!=4:
        raise ValueError('Invalid map viewport.')
    south,north,west,east=map(float,raw)
    if not all(math.isfinite(v) for v in (south,north,west,east)):
        raise ValueError('Invalid map viewport.')
    south,north=max(-89.999,south),min(89.999,north)
    west,east=max(-179.999,west),min(179.999,east)
    if south>=north or west>=east:
        raise ValueError('The map viewport is outside the supported Mars extent.')
    return south,north,west,east


def padded_view_bounds(raw):
    south,north,west,east=view_bounds(raw)
    dy,dx=(north-south)*.35,(east-west)*.35
    return view_bounds((south-dy,north+dy,west-dx,east+dx))


def covers(outer,inner):
    a,b,c,d=outer;s,n,w,e=view_bounds(inner)
    return a<=s and b>=n and c<=w and d>=e


def load_view_grid(loader,bounds):
    """Split wide views so an elevation profile never wraps across the planet."""
    south,north,west,east=view_bounds(bounds)
    count=max(1,math.ceil((east-west)/90))
    edges=np.linspace(west,east,count+1)
    parts=[];latitudes=None
    for index in range(count):
        xs,ys,z=loader(south,north,float(edges[index]),float(edges[index+1]))
        xs,ys,z=np.asarray(xs,dtype=float),np.asarray(ys,dtype=float),np.asarray(z,dtype=float)
        if z.shape!=(len(ys),len(xs)):
            raise ValueError('Viewport elevations do not match the sample grid.')
        if latitudes is not None and not np.array_equal(ys,latitudes):
            raise ValueError('Viewport elevation strips use different latitude grids.')
        latitudes=ys
        parts.append((xs if index==0 else xs[1:],z if index==0 else z[:,1:]))
    return np.concatenate([p[0] for p in parts]),latitudes,np.concatenate([p[1] for p in parts],axis=1)
