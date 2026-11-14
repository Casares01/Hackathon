import csv
import io
import math
import os
import urllib.error
import urllib.request
import re 

MARS_TREK_NOMENCLATURE_URL = (
    "https://planetarynames.wr.usgs.gov/SearchResults?target=Mars&output=CSV"
)
ARCHIVO_CACHE = "mars_trek_nomenclature.csv"
RADIO_MARTE_KM = 3389.5
TIPOS_VOLCANICOS = ("mons", "tholus", "patera", "montes", "tholi", "paterae")


def obtener_datos_mars_trek():
    """Lee el CSV local si existe; si no, intenta descargarlo."""
    ruta_archivo = os.path.join(os.path.dirname(os.path.abspath(__file__)), ARCHIVO_CACHE)

    if os.path.exists(ruta_archivo):
        print(f"Leyendo datos locales desde '{ARCHIVO_CACHE}'...")
        with open(ruta_archivo, "r", encoding="utf-8-sig", errors="replace") as f:
            return f.read()

    print("Intentando descargar datos desde USGS / Mars Trek...")
    req = urllib.request.Request(
        MARS_TREK_NOMENCLATURE_URL,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as respuesta:
            contenido = respuesta.read().decode("utf-8-sig", errors="replace")
        with open(ruta_archivo, "w", encoding="utf-8", newline="") as f:
            f.write(contenido)
        return contenido
    except urllib.error.HTTPError as e:
        print(f"\n[Error del servidor {e.code}]: Descarga el CSV manualmente y guárdalo como:\n  {ruta_archivo}")
        return None
    except Exception as e:
        print(f"\n[Error de conexión]: {e}")
        return None


def normalizar_longitud_180(lon):
    lon = lon % 360.0
    if lon > 180.0:
        lon -= 360.0
    return lon


def distancia_marte_km(lat1, lon1, lat2, lon2):
    lat1_r, lon1_r = math.radians(lat1), math.radians(normalizar_longitud_180(lon1))
    lat2_r, lon2_r = math.radians(lat2), math.radians(normalizar_longitud_180(lon2))

    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return RADIO_MARTE_KM * c


def obtener_campo(fila_norm, posibles_nombres):
    for nombre in posibles_nombres:
        if nombre in fila_norm and fila_norm[nombre] != "":
            return fila_norm[nombre]
    return ""


# Códigos oficiales de USGS (MO=Mons, TH=Tholus, PA=Patera) y nombres completos
TIPOS_VOLCANICOS = ("mons", "tholus", "patera", "montes", "tholi", "paterae")
CODIGOS_VOLCANICOS = {"mo", "th", "pa"}


def limpiar_numero(texto):
    """Extrae el valor numérico decimal aunque tenga símbolos como ° o espacios."""
    if not texto:
        return None
    texto = texto.replace(",", ".")
    coincidencia = re.search(r"[-+]?\d*\.?\d+", texto)
    return float(coincidencia.group()) if coincidencia else None


def cargar_volcanes(csv_texto):
    if not csv_texto:
        return []

    if "<html" in csv_texto.lower():
        print("[Aviso] El archivo contiene HTML en lugar de datos CSV válidos.")
        return []

    primera_linea = csv_texto.splitlines()[0] if csv_texto.splitlines() else ""
    delimitador = ";" if primera_linea.count(";") > primera_linea.count(",") else ","

    lector = csv.DictReader(io.StringIO(csv_texto), delimiter=delimitador)
    volcanes = []
    total_filas = 0

    for fila in lector:
        total_filas += 1
        # Compactar múltiples espacios o espacios duros (\xa0) en un solo espacio
        fila_norm = {
            re.sub(r"\s+", " ", k.replace("_", " ")).strip().lower(): (
                v.strip() if isinstance(v, str) else ""
            )
            for k, v in fila.items()
            if k is not None
        }

        tipo = obtener_campo(fila_norm, ["feature type", "type"]).lower().strip()
        es_volcan = (tipo in CODIGOS_VOLCANICOS) or any(t in tipo for t in TIPOS_VOLCANICOS)

        if es_volcan:
            lat = limpiar_numero(obtener_campo(fila_norm, ["center lat", "center latitude", "latitude", "lat"]))
            lon_360 = limpiar_numero(
                obtener_campo(
                    fila_norm,
                    ["center lon", "center longitude", "center longitude (0 - 360)", "longitude", "lon"],
                )
            )
            diametro = limpiar_numero(obtener_campo(fila_norm, ["diameter", "diameter (km)"])) or 0.0
            nombre = obtener_campo(fila_norm, ["clean feature name", "feature name", "name"]) or "Desconocido"

            if lat is not None and lon_360 is not None:
                volcanes.append({
                    "nombre": nombre,
                    "tipo": tipo.upper() if tipo in CODIGOS_VOLCANICOS else tipo.title(),
                    "lat": lat,
                    "lon_360": lon_360,
                    "lon_180": normalizar_longitud_180(lon_360),
                    "diametro_km": diametro,
                })

    print(f"[Diagnóstico] Filas leídas: {total_filas} | Volcanes cargados: {len(volcanes)}")
    return volcanes


def buscar_volcanes_cercanos(lat_objetivo, lon_objetivo, top_n=5):
    csv_texto = obtener_datos_mars_trek()
    volcanes = cargar_volcanes(csv_texto)

    resultados = []
    for v in volcanes:
        dist = distancia_marte_km(lat_objetivo, lon_objetivo, v["lat"], v["lon_360"])
        resultados.append((dist, v))

    resultados.sort(key=lambda x: x[0])
    return resultados[:top_n]


if __name__ == "__main__":
    print("--- Buscador de Volcanes Cercanos en Marte (Datos Mars Trek) ---")
    lat_usuario = float(input("Introduce la Latitud (-90 a 90, ej. 20): "))
    lon_usuario = float(input("Introduce la Longitud (-180 a 360, ej. 20): "))
    cantidad = int(input("¿Cuántos volcanes cercanos quieres ver? [5]: ") or 5)

    cercanos = buscar_volcanes_cercanos(lat_usuario, lon_usuario, top_n=cantidad)

    if cercanos:
        print(
            f"\nLos {len(cercanos)} volcanes más cercanos a "
            f"({lat_usuario}°, {normalizar_longitud_180(lon_usuario):.2f}° E):\n"
        )
        print(f"{'#':<3} {'Nombre':<24} {'Tipo':<18} {'Lat / Lon (180°)':<22} {'Diámetro':<12} {'Distancia'}")
        print("-" * 95)

        for idx, (dist, v) in enumerate(cercanos, start=1):
            coords = f"{v['lat']:>6.2f}°, {v['lon_180']:>7.2f}°"
            print(
                f"{idx:<3} {v['nombre']:<24} {v['tipo']:<18} {coords:<22} "
                f"{v['diametro_km']:>7.1f} km   {dist:>8.2f} km"
            )