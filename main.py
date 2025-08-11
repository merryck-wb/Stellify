import io
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import imageio
import matplotlib.pyplot as plt
import requests
from geopy import Nominatim
from pytz import timezone, utc
from skyfield.api import Star, load, Loader, wgs84
from skyfield.data import hipparcos
from skyfield.projections import build_stereographic_projection


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
CACHE_FILE = BASE_DIR / "location_cache.json"

DEFAULT_CHART_SIZE = 12
DEFAULT_MAX_STAR_SIZE = 100

def load_data():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    loader = Loader(str(DATA_DIR))

    # de421 shows position of earth and sun in space
    eph = loader('de421.bsp')
    # hipparcos dataset
    with loader.open(hipparcos.URL) as f:
        stars = hipparcos.load_dataframe(f)
    # Load constellations data from Stellarium
    # This is a URL to the modern constellation data in JSON format
    url = 'https://raw.githubusercontent.com/Stellarium/stellarium/master/skycultures/modern_st/index.json'
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    
    # Extract constellation lines
    edges = []
    for constellation in data.get('constellations', []):
        lines = constellation.get('lines', [])
        for line in lines:
            for i in range(len(line) - 1):
                edges.append((line[i], line[i + 1]))

    return eph, stars, edges

def get_coordinates(location):
    cache = {}
    # Check if cache file exists and load it
    if CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text())
        except json.JSONDecodeError:
            pass  # corrupt cache — just rebuild

    # If location is already cached, return it
    if location in cache:
        return tuple(cache[location])

    # Use geopy to get coordinates from location name
    locator = Nominatim(user_agent='star_map_locator')
    loc = locator.geocode(location)
    if not loc:
        raise ValueError(f"Location '{location}' not found")
    coords = (loc.latitude, loc.longitude)

    # Save the coordinates to cache
    cache[location] = coords
    CACHE_FILE.write_text(json.dumps(cache))
    return coords

def get_timezone(lat, lon):
    # Use timeapi.io to get timezone from coordinates
    url = f"https://timeapi.io/api/TimeZone/coordinate?latitude={lat}&longitude={lon}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data["timeZone"]
    except (requests.RequestException, KeyError) as e:
        raise RuntimeError(f"Failed to retrieve timezone data")
    
def collect_celestial_data(location, when):
    eph, stars, edges = load_data()

    # Get coordinates for the location
    lat, lon = get_coordinates(location)

    # Get timezone for the location
    timezone_str = get_timezone(lat, lon)
    local = timezone(timezone_str)
    dt = datetime.strptime(when, '%Y-%m-%d %H:%M:%S')
    utc_dt = local.localize(dt).astimezone(utc)

    # Convert to UTC based on location's timezone
    t = load.timescale().from_datetime(utc_dt)
    observer = wgs84.latlon(lat, lon).at(t)
    ra, dec, _ = observer.radec()
    center_object = Star(ra=ra, dec=dec)

    # Create a stereographic projection centered on the observer's position
    center = eph['earth'].at(t).observe(center_object)
    projection = build_stereographic_projection(center)

    # Compute the x and y coordinates based on the projection
    star_positions = eph['earth'].at(t).observe(Star.from_dataframe(stars))
    x, y = projection(star_positions)
    stars['x'] = x
    stars['y'] = y

    # Create edges for constellations
    valid_edges = [(s1, s2) for s1, s2 in edges if s1 in stars.index and s2 in stars.index]
    edges_star1 = [s1 for s1, s2 in valid_edges]
    edges_star2 = [s2 for s1, s2 in valid_edges]

    return stars, edges_star1, edges_star2

def generate_star_map(location, when, chart_size=DEFAULT_CHART_SIZE, max_star_size=DEFAULT_MAX_STAR_SIZE):
    stars, edges_star1, edges_star2 = collect_celestial_data(location, when)

    # Define the number of stars and brightness of stars to include
    limiting_magnitude = 10
    bright_stars = (stars.magnitude <= limiting_magnitude)
    magnitude = stars['magnitude'][bright_stars]
    marker_size = max_star_size * 10 ** (magnitude / -2.5)

    # Build the figure
    fig, ax = plt.subplots(figsize=(chart_size, chart_size), facecolor='#041A40')

    # Draw the stars
    ax.scatter(
        stars['x'][bright_stars], stars['y'][bright_stars],
        s=marker_size, color='white', marker='.', linewidth=0, zorder=2
    )
    # Draw the constellation lines
    xy1 = stars.loc[edges_star1][['x', 'y']].values
    xy2 = stars.loc[edges_star2][['x', 'y']].values
    for (x1, y1), (x2, y2) in zip(xy1, xy2):
        ax.plot([x1, x2], [y1, y2], color='white', lw=0.15, alpha=0.7, zorder=3)

    # Various settings for the plot
    ax.set_aspect('equal')
    ax.set_xlim(-1, 1)
    ax.set_ylim(-1, 1)
    plt.axis('off')

    # Set the title with location and time
    when_datetime = datetime.strptime(when, '%Y-%m-%d %H:%M:%S')
    ax.set_title(
        f"Observation Location: {location}\nTime: {when_datetime.strftime('%Y-%m-%d %H:%M')}",
        color='white',
        fontsize=10
    )

    return fig

def generate_star_map_png(location, when, chart_size=DEFAULT_CHART_SIZE, max_star_size=DEFAULT_MAX_STAR_SIZE, output_path=None):
    # Generate the star map figure
    fig = generate_star_map(location, when, chart_size, max_star_size)

    # Save the figure to a PNG file
    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        when_datetime = datetime.strptime(when, '%Y-%m-%d %H:%M:%S')
        filename = f"{location}_{when_datetime.strftime('%Y%m%d_%H%M')}.png"
        output_path = OUTPUT_DIR / filename
    fig.savefig(output_path, format='png', dpi=1200, bbox_inches='tight')
    plt.close(fig)

def _generate_frame(args):
    location, when_str, chart_size, max_star_size = args
    fig = generate_star_map(location, when_str, chart_size, max_star_size)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return imageio.v2.imread(buf)

def generate_star_map_gif(location, when, hours, step_minutes, chart_size=DEFAULT_CHART_SIZE, max_star_size=DEFAULT_MAX_STAR_SIZE):
    start_dt = datetime.strptime(when, '%Y-%m-%d %H:%M:%S')
    total_frames = int((hours * 60) / step_minutes)
    times = [start_dt + timedelta(minutes=i * step_minutes) for i in range(total_frames)]

    # Prepare arguments for each process
    args_list = [
        (location, t.strftime('%Y-%m-%d %H:%M:%S'), chart_size, max_star_size)
        for t in times
    ]

    # Use all CPU cores
    cpu_count = multiprocessing.cpu_count()
    with ProcessPoolExecutor(max_workers=cpu_count) as executor:
        images = list(executor.map(_generate_frame, args_list))

    # Save as GIF
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{location}_{start_dt.strftime('%Y%m%d_%H%M')}.gif"
    gif_path = OUTPUT_DIR / filename
    imageio.mimsave(gif_path, images, duration=step_minutes * 60 / 10)