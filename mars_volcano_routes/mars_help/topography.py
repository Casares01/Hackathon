"""Georeferenced elevation shading and labelled contours from sampled Mars elevations."""
import base64
from io import BytesIO
import math

import numpy as np
from matplotlib.figure import Figure
from matplotlib.colors import LinearSegmentedColormap


def contour_interval(span):
    if span<=0:
        return 1.0
    target=span/9
    magnitude=10**math.floor(math.log10(target))
    return min((1,2,5,10),key=lambda step:abs(step*magnitude-target))*magnitude


def terrain_overlay(xs,ys,elevations,*,contours_only=False):
    x,y,z=np.asarray(xs),np.asarray(ys),np.asarray(elevations,dtype=float)
    if x.ndim!=1 or y.ndim!=1 or z.shape!=(len(y),len(x)) or len(x)<2 or len(y)<2:
        raise ValueError('Topographic data must match the longitude and latitude grid.')
    finite=z[np.isfinite(z)]
    if not finite.size:
        raise ValueError('No elevation samples are available for a topographic map.')
    low,high=float(finite.min()),float(finite.max())
    interval=contour_interval(high-low)
    palette=['#294957','#527b7a','#91a796','#d8cda7','#b8946b','#785a46']
    cmap=LinearSegmentedColormap.from_list('mars_terrain',palette)
    fig=Figure(figsize=(12,7),dpi=140)
    ax=fig.add_axes((0,0,1,1))
    masked=np.ma.masked_invalid(z)
    if not contours_only:
        if low==high:
            ax.pcolormesh(x,y,masked,cmap=cmap,vmin=low-.5,vmax=high+.5,shading='nearest',rasterized=True)
        else:
            ax.contourf(x,y,masked,levels=np.linspace(low,high,65),cmap=cmap,vmin=low,vmax=high,corner_mask=False)
    levels=np.arange(math.ceil(low/interval)*interval,high,interval)
    if levels.size:
        if contours_only:
            ax.contour(x,y,masked,levels=levels,colors='#ffffff',linewidths=1.8,alpha=.85)
        contour=ax.contour(x,y,masked,levels=levels,colors='#263b3b',linewidths=.65,alpha=.75)
        labels=ax.clabel(contour,inline=True,fontsize=8,fmt=lambda value:f'{value:,.0f}' if interval>=1 else f'{value:.2f}')
        for text in labels:
            text.set_bbox(dict(facecolor='#f7f4e8',edgecolor='none',alpha=.8,pad=1.5))
    ax.set_xlim(float(x[0]),float(x[-1]));ax.set_ylim(float(y[0]),float(y[-1]));ax.set_axis_off()
    buffer=BytesIO();fig.savefig(buffer,format='png',transparent=True)
    return dict(image='data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode('ascii'),bounds=[float(y[0]),float(y[-1]),float(x[0]),float(x[-1])],minimum_m=low,maximum_m=high,contour_interval_m=float(interval),palette=palette,render_mode='contours' if contours_only else 'shaded',has_contours=bool(levels.size),source='MGS MOLA · route elevation grid')
