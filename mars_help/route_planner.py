"""Experimental route planning over a coarse Martian elevation grid.

Not suitable for astronaut/rover safety or operational route certification.
Elevation values are derived from NASA Mars Trek samples, not ground-truth hazards.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
import numpy as np

MARS_RADIUS_M = 3_390_000.0


@dataclass
class RouteResult:
    coordinates: list[tuple[float, float]]  # (longitude, latitude)
    distance_m: float
    ascent_m: float
    descent_m: float
    maximum_slope_percent: float
    requested_distance_m: float
    start: tuple[float, float]
    end: tuple[float, float]
    source: str = "MGS MOLA (Mars Trek profile samples)"


def _step_metres(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    a1, a2 = math.radians(lat1), math.radians(lat2)
    da = a2-a1
    db = math.radians(((lon2-lon1+180) % 360)-180)
    h = math.sin(da/2)**2 + math.cos(a1)*math.cos(a2)*math.sin(db/2)**2
    return 2*MARS_RADIUS_M*math.asin(min(1.0, math.sqrt(max(0.0,h))))


def plan_route(
    longitudes,
    latitudes,
    elevations,
    *,
    start_lon: float,
    start_lat: float,
    target_distance_km: float,
    max_slope_percent: float = 15.0,
    max_ascent_m: float | None = None,
    distance_tolerance: float = 0.20,
    max_states: int = 120_000,
) -> RouteResult:
    """Find an approximate one-way route from a start point.

    Uses an 8-connected grid with forbidden edges exceeding max local slope.
    Explores non-dominated (distance, ascent) states. The endpoint is free and
    selected to approximate target_distance_km. Routes are not verified walkable.
    """
    xs = np.asarray(longitudes, dtype=float)
    ys = np.asarray(latitudes, dtype=float)
    z = np.asarray(elevations, dtype=float)
    if xs.ndim != 1 or ys.ndim != 1 or z.shape != (len(ys),len(xs)):
        raise ValueError("Las elevaciones deben tener forma (n_latitudes, n_longitudes).")
    if len(xs) < 2 or len(ys) < 2 or not np.all(np.diff(xs)>0) or not np.all(np.diff(ys)>0):
        raise ValueError("Las coordenadas deben ser crecientes y tener al menos 2 valores por eje.")
    if z.size > 20_000:
        raise ValueError("Cuadrícula demasiado grande; reduce filas o columnas.")
    if not (math.isfinite(target_distance_km) and target_distance_km > 0):
        raise ValueError("La distancia debe ser positiva.")
    if not (math.isfinite(max_slope_percent) and max_slope_percent >= 0):
        raise ValueError("La pendiente máxima debe ser >= 0.")
    if max_ascent_m is not None and (not math.isfinite(max_ascent_m) or max_ascent_m < 0):
        raise ValueError("El desnivel positivo máximo debe ser >= 0.")
    if not (0 <= distance_tolerance <= 1):
        raise ValueError("La tolerancia debe estar entre 0 y 1.")

    requested_m = target_distance_km*1000.0
    # Search a little beyond the target; do not keep extending arbitrarily.
    limit_m = requested_m*(1+max(distance_tolerance,0.1))+max(
        _step_metres(float(xs[0]),float(ys[0]),float(xs[1]),float(ys[1])),
        _step_metres(float(xs[0]),float(ys[0]),float(xs[0]),float(ys[1]))
    )
    si=int(np.argmin(abs(ys-start_lat)))
    sj=int(np.argmin(abs(xs-start_lon)))
    if not np.isfinite(z[si,sj]):
        valid=np.argwhere(np.isfinite(z))
        if len(valid)==0:
            raise ValueError("No hay elevaciones válidas.")
        # Nearest valid cell by physical distance.
        si,sj=map(int,min(valid,key=lambda p:_step_metres(float(xs[p[1]]),float(ys[p[0]]),start_lon,start_lat)))

    # A label represents distance, accumulated positive ascent, parent label and cell.
    # Retain at most 20 useful labels per cell to keep computation bounded.
    labels = []
    per_cell: dict[tuple[int,int],list[int]] = {}
    heap=[]
    def offer(i,j,d,up,down,maximum,parent):
        cell=(i,j)
        prior=per_cell.get(cell,[])
        # approximate Pareto dominance, protects useful low-ascent alternatives
        if any(labels[k][0] <= d+1e-8 and labels[k][1] <= up+1e-8 for k in prior):
            return
        # Clean dominated labels and bound per-cell state count.
        prior=[k for k in prior if not (d <= labels[k][0]+1e-8 and up <= labels[k][1]+1e-8)]
        if len(prior)>=20:
            worst=max(prior,key=lambda k: labels[k][0]/max(requested_m,1)+labels[k][1]/max(max_ascent_m or 300,1))
            if d/max(requested_m,1)+up/max(max_ascent_m or 300,1) >= labels[worst][0]/max(requested_m,1)+labels[worst][1]/max(max_ascent_m or 300,1):
                return
            prior.remove(worst)
        k=len(labels)
        labels.append((d,up,down,maximum,parent,i,j))
        prior.append(k)
        per_cell[cell]=prior
        heapq.heappush(heap,(d,k))
    offer(si,sj,0.0,0.0,0.0,0.0,None)
    best_id=None
    best_error=float('inf')
    handled=0
    moves=[(di,dj) for di in (-1,0,1) for dj in (-1,0,1) if di or dj]
    while heap and handled<max_states:
        d,k=heapq.heappop(heap)
        old_d,up,down,mx,parent,i,j=labels[k]
        if k not in per_cell.get((i,j),[]):
            continue
        handled+=1
        if d>0:
            err=abs(d-requested_m)
            if err<best_error:
                best_error=err
                best_id=k
            if err <= 0.5 * min(
                _step_metres(float(xs[max(j-1,0)]),float(ys[i]),float(xs[j]),float(ys[i])) if j else float('inf'),
                _step_metres(float(xs[j]),float(ys[max(i-1,0)]),float(xs[j]),float(ys[i])) if i else float('inf')
            ):
                # Keep checking alternatives, not a hard guarantee of closest optimum.
                pass
        for di,dj in moves:
            ni,nj=i+di,j+dj
            if not (0<=ni<len(ys) and 0<=nj<len(xs)) or not np.isfinite(z[ni,nj]):
                continue
            horizontal=_step_metres(float(xs[j]),float(ys[i]),float(xs[nj]),float(ys[ni]))
            if horizontal<=0: continue
            delta=float(z[ni,nj]-z[i,j])
            slope=abs(delta)/horizontal*100.0
            if slope>max_slope_percent: continue
            next_up=up+max(delta,0.0)
            if max_ascent_m is not None and next_up>max_ascent_m: continue
            nd=d+math.hypot(horizontal,delta)
            if nd>limit_m: continue
            offer(ni,nj,nd,next_up,down+max(-delta,0.0),max(mx,slope),k)
    if best_id is None:
        raise ValueError("No se encontró ruta: aumenta el área o permite más pendiente/desnivel.")
    rec=labels[best_id]
    if abs(rec[0]-requested_m)>requested_m*distance_tolerance:
        raise ValueError(
            f"No hay ruta de {target_distance_km:g} km dentro de ±{distance_tolerance*100:.0f}%. "
            f"La más cercana calculada mide {rec[0]/1000:.2f} km."
        )
    path=[]
    k=best_id
    while k is not None:
        ld,lu,down,mx,parent,i,j=labels[k]
        path.append((float(xs[j]),float(ys[i])))
        k=parent
    path.reverse()
    return RouteResult(path,rec[0],rec[1],rec[2],rec[3],requested_m,path[0],path[-1])
