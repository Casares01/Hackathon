import json
import requests
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from io import BytesIO
import math
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor, as_completed


class MarsElevationAPI:

    BASE_URL = (
        "https://trek.nasa.gov/mars/"
        "TrekServices/ws/elevationProfile/multiDEM"
    )

    MARS_RADIUS = 3390000

    def __init__(self):
        self.session = requests.Session()

    def get_profile(self, coordinates, number_of_points=100):

        if len(coordinates) < 2:
            raise ValueError("At least two coordinates are required")

        # Normalize longitude automatically
        coordinates = [
            [
                ((lon + 180) % 360) - 180,
                lat
            ]
            for lon, lat in coordinates
        ]

        params = {
            "path": json.dumps(coordinates),
            "numberOfPoints": number_of_points,
            "radiusInMeters": self.MARS_RADIUS
        }

        response = self.session.get(
            self.BASE_URL,
            params=params,
            timeout=60
        )

        response.raise_for_status()

        return response.json()

    def get_available_dems(self, profile):
        """Return the names of available elevation models."""

        return [
            path["DEM"]
            for path in profile.get("paths", [])
        ]

    def get_elevation_grid(
        self,
        min_lat,
        max_lat,
        min_lon,
        max_lon,
        rows=10,
        columns=50,
        dem_name="MGS MOLA, Global DEM"
    ):

        latitudes = np.linspace(min_lat, max_lat, rows)
        longitudes = np.linspace(min_lon, max_lon, columns)

        grid = np.full((rows, columns), np.nan)

        def fetch_row(i, lat):

            profile = self.get_profile(
                coordinates=[
                    [min_lon, float(lat)],
                    [max_lon, float(lat)]
                ],
                number_of_points=columns
            )

            paths = [
                p for p in profile.get("paths", [])
                if p.get("DEM") == dem_name
            ]

            if not paths:
                return i, None

            no_data = profile.get("No_Data_Value", -32768)

            points = [
                p for p in paths[0]["line"]
                if (
                    p.get("elevation") is not None
                    and p["elevation"] != no_data
                )
            ]

            if len(points) < 2:
                return i, None

            x = np.array([p["x"] for p in points])
            z = np.array([p["elevation"] for p in points])

            order = np.argsort(x)
            x, z = x[order], z[order]

            x, indices = np.unique(x, return_index=True)
            z = z[indices]

            if len(x) < 2:
                return i, None

            values = np.interp(
                longitudes,
                x,
                z,
                left=np.nan,
                right=np.nan
            )

            return i, values

        with ThreadPoolExecutor(max_workers=4) as executor:

            futures = [
                executor.submit(fetch_row, i, float(lat))
                for i, lat in enumerate(latitudes)
            ]

            for future in as_completed(futures):
                i, values = future.result()

                if values is not None:
                    grid[i] = values

        return longitudes, latitudes, grid

    def plot_contours(
        self,
        longitudes,
        latitudes,
        grid,
        interval=20,
        title="Mars Topographic Map",
        save_path=None
    ):
        """Generate contour lines from an elevation grid."""

        valid = np.isfinite(grid)

        if not np.any(valid):
            raise ValueError("No valid elevation data found")

        minimum = np.nanmin(grid)
        maximum = np.nanmax(grid)

        levels = np.arange(
            np.ceil(minimum / interval) * interval,
            maximum + interval,
            interval
        )

        if len(levels) == 0:
            raise ValueError(
                "Elevation range is too small for contour generation"
            )

        fig, ax = plt.subplots(figsize=(12, 9))

        image = ax.pcolormesh(
            longitudes,
            latitudes,
            np.ma.masked_invalid(grid),
            shading="auto",
            cmap="terrain"
        )

        contours = ax.contour(
            longitudes,
            latitudes,
            np.ma.masked_invalid(grid),
            levels=levels,
            colors="black",
            linewidths=0.5
        )

        ax.clabel(
            contours,
            inline=True,
            fontsize=7
        )

        fig.colorbar(
            image,
            ax=ax,
            label="Elevation (m)"
        )

        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_title(title)

        if save_path:
            fig.savefig(
                save_path,
                dpi=300,
                bbox_inches="tight"
            )

        return fig, ax

    def get_satellite_image(
        self,
        min_lat,
        max_lat,
        min_lon,
        max_lon,
        zoom=7
    ):
        """
        Download a satellite image from NASA Mars Trek.

        Returns a PIL image covering the requested area.
        Uses the global Viking colour mosaic.
        """

        base_url = (
            "https://trek.nasa.gov/tiles/Mars/EQ/"
            "Mars_Viking_MDIM21_ClrMosaic_global_232m/"
            "1.0.0/default/default028mm"
        )

        if not (-180 <= min_lon < max_lon <= 180):
            raise ValueError("Longitude range must be within -180 to 180")

        if not (-90 <= min_lat < max_lat <= 90):
            raise ValueError("Latitude range must be within -90 to 90")

        if not (0 <= zoom <= 7):
            raise ValueError("Zoom must be between 0 and 7")

        tile_size = 256

        # Equirectangular WMTS tile grid
        num_cols = 2 ** (zoom + 1)
        num_rows = 2 ** zoom

        world_width = num_cols * tile_size
        world_height = num_rows * tile_size

        def lon_to_x(lon):
            return (lon + 180) / 360 * world_width

        def lat_to_y(lat):
            return (90 - lat) / 180 * world_height

        x0 = lon_to_x(min_lon)
        x1 = lon_to_x(max_lon)
        y0 = lat_to_y(max_lat)
        y1 = lat_to_y(min_lat)

        col_min = int(x0 // tile_size)
        col_max = int((x1 - 1e-9) // tile_size)

        row_min = int(y0 // tile_size)
        row_max = int((y1 - 1e-9) // tile_size)

        width = (col_max - col_min + 1) * tile_size
        height = (row_max - row_min + 1) * tile_size

        mosaic = Image.new("RGB", (width, height), (30, 30, 30))

        for row in range(row_min, row_max + 1):
            for col in range(col_min, col_max + 1):

                url = f"{base_url}/{zoom}/{row}/{col}.jpg"

                response = self.session.get(url, timeout=30)
                response.raise_for_status()

                tile = Image.open(BytesIO(response.content))
                tile.load()

                x = (col - col_min) * tile_size
                y = (row - row_min) * tile_size

                mosaic.paste(tile.convert("RGB"), (x, y))

        # Crop to the requested geographic boundaries
        crop_box = (
            int(math.floor(x0 - col_min * tile_size)),
            int(math.floor(y0 - row_min * tile_size)),
            int(math.ceil(x1 - col_min * tile_size)),
            int(math.ceil(y1 - row_min * tile_size))
        )

        return mosaic.crop(crop_box)

    def plot_topography_with_image(
        self,
        longitudes,
        latitudes,
        grid,
        interval=20,
        title="Mars Topographic Explorer",
        save_path=None
    ):
        """
        Display a topographic map and satellite image
        of the same location side by side.
        """

        import numpy as np
        import matplotlib.pyplot as plt

        min_lon = float(np.min(longitudes))
        max_lon = float(np.max(longitudes))
        min_lat = float(np.min(latitudes))
        max_lat = float(np.max(latitudes))

        # Download satellite image
        satellite = self.get_satellite_image(
            min_lat=min_lat,
            max_lat=max_lat,
            min_lon=min_lon,
            max_lon=max_lon
        )

        # Create two panels
        fig, axes = plt.subplots(
            1, 2,
            figsize=(16, 7),
            constrained_layout=True
        )

        ax1, ax2 = axes

        valid = np.ma.masked_invalid(grid)

        minimum = np.nanmin(grid)
        maximum = np.nanmax(grid)

        levels = np.arange(
            np.ceil(minimum / interval) * interval,
            maximum,
            interval
        )

        # LEFT: TOPOGRAPHIC MAP
        image = ax1.pcolormesh(
            longitudes,
            latitudes,
            valid,
            shading="auto",
            cmap="terrain"
        )

        if len(levels) > 0:
            contours = ax1.contour(
                longitudes,
                latitudes,
                valid,
                levels=levels,
                colors="black",
                linewidths=0.5
            )

            ax1.clabel(
                contours,
                fontsize=7
            )

        ax1.set_title("Topographic Map — 20 m Contours")
        ax1.set_xlabel("Longitude (°)")
        ax1.set_ylabel("Latitude (°)")

        fig.colorbar(
            image,
            ax=ax1,
            label="Elevation (m)",
            shrink=0.8
        )

        # RIGHT: SATELLITE IMAGE
        ax2.imshow(
            satellite,
            extent=[
                min_lon,
                max_lon,
                min_lat,
                max_lat
            ],
            origin="upper"
        )

        ax2.set_title("NASA Mars Trek — Satellite Image")
        ax2.set_xlabel("Longitude (°)")
        ax2.set_ylabel("Latitude (°)")

        # Keep matching geographic boundaries
        for ax in axes:
            ax.set_xlim(min_lon, max_lon)
            ax.set_ylim(min_lat, max_lat)

        fig.suptitle(title, fontsize=16)

        if save_path:
            fig.savefig(
                save_path,
                dpi=300,
                bbox_inches="tight"
            )

        return fig, axes

    def generate_map(
        self,
        latitude,
        longitude,
        radius=0.05,
        interval=20,
        save_path=None
    ):
        longitude = ((longitude + 180) % 360) - 180

        print("Retrieving NASA elevation data...")

        lon, lat, grid = self.get_elevation_grid(
            min_lat=latitude - radius,
            max_lat=latitude + radius,
            min_lon=longitude - radius,
            max_lon=longitude + radius,
            rows=30,
            columns=100
        )

        print("Downloading satellite image...")

        fig, axes = self.plot_topography_with_image(
            longitudes=lon,
            latitudes=lat,
            grid=grid,
            interval=interval,
            title="Mars Topographic Map",
            save_path=save_path
        )

        return fig, axes

    def plot_interactive_map(
        self,
        longitudes,
        latitudes,
        grid,
        interval=20,
        show_colors=True,
        show_contours=True
    ):

        fig = go.Figure()
        z = np.asarray(grid, dtype=float)

        # Elevation colors
        if show_colors:
            fig.add_trace(
                go.Heatmap(
                    x=longitudes,
                    y=latitudes,
                    z=z,
                    colorscale="Earth",
                    colorbar=dict(title="Elevation (m)"),
                    name="Elevation"
                )
            )

        # Contour lines
        if show_contours:
            minimum = np.nanmin(z)
            maximum = np.nanmax(z)

            start = np.ceil(minimum / interval) * interval
            end = np.floor(maximum / interval) * interval

            if start <= end:
                fig.add_trace(
                    go.Contour(
                        x=longitudes,
                        y=latitudes,
                        z=z,
                        contours=dict(
                            start=start,
                            end=end,
                            size=interval,
                            coloring="none",
                            showlabels=True
                        ),
                        line=dict(
                            color="black",
                            width=1.5
                        ),
                        showscale=False,
                        name="Contour lines"
                    )
                )

        fig.update_layout(
            title="Mars Topographic Map",
            xaxis_title="Longitude (°)",
            yaxis_title="Latitude (°)",
            height=650,
            dragmode="pan",

            # WHITE BACKGROUND
            plot_bgcolor="white",
            paper_bgcolor="white",
        )

        fig.update_xaxes(
            showgrid=False,
            zeroline=False
        )

        fig.update_yaxes(
            showgrid=False,
            zeroline=False
        )

        fig.update_layout(
            uirevision="mars-map"
        )

        return fig