import matplotlib.pyplot as plt
from skyfield.api import load, Star, wgs84
from skyfield.data import hipparcos
from skyfield.projections import build_stereographic_projection
from geopy import Nominatim
from datetime import datetime, timedelta
from pytz import timezone, utc
import requests
import os
import json
from pathlib import Path
import imageio
import io

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
CACHE_FILE = BASE_DIR / "location_cache.json"

DEFAULT_CHART_SIZE = 12
DEFAULT_MAX_STAR_SIZE = 100

from skyfield.api import Loader

def load_data():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    loader = Loader(str(DATA_DIR))
    eph = loader('de421.bsp')
    with loader.open(hipparcos.URL) as f:
        stars = hipparcos.load_dataframe(f)

    return eph, stars

def get_coordinates(location):
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
    else:
        cache = {}

    if location in cache:
        return cache[location]

    locator = Nominatim(user_agent='star_map_locator')
    loc = locator.geocode(location)
    coords = (loc.latitude, loc.longitude)

    cache[location] = coords
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

    return coords

def get_timezone(lat, lon):
    url = f"https://timeapi.io/api/TimeZone/coordinate?latitude={lat}&longitude={lon}"
    response = requests.get(url).json()
    return response["timeZone"]

def collect_celestial_data(location, when):
    eph, stars = load_data()
    lat, lon = get_coordinates(location)

    timezone_str = get_timezone(lat, lon)
    local = timezone(timezone_str)
    dt = datetime.strptime(when, '%Y-%m-%d %H:%M:%S')
    utc_dt = local.localize(dt).astimezone(utc)

    t = load.timescale().from_datetime(utc_dt)
    observer = wgs84.latlon(lat, lon).at(t)
    ra, dec, _ = observer.radec()
    center_object = Star(ra=ra, dec=dec)

    center = eph['earth'].at(t).observe(center_object)
    projection = build_stereographic_projection(center)

    star_positions = eph['earth'].at(t).observe(Star.from_dataframe(stars))
    x, y = projection(star_positions)
    stars['x'] = x
    stars['y'] = y

    return stars

def generate_star_map(location, when, chart_size=DEFAULT_CHART_SIZE, max_star_size=DEFAULT_MAX_STAR_SIZE):
    stars = collect_celestial_data(location, when)

    limiting_magnitude = 6.5
    bright_stars = (stars.magnitude <= limiting_magnitude)
    magnitude = stars['magnitude'][bright_stars]
    marker_size = max_star_size * 10 ** (magnitude / -2.5)

    fig, ax = plt.subplots(figsize=(chart_size, chart_size), facecolor='#041A40')

    ax.scatter(
        stars['x'][bright_stars], stars['y'][bright_stars],
        s=marker_size, color='white', marker='.', linewidth=0, zorder=2
    )

    ax.set_aspect('equal')
    ax.set_xlim(-1, 1)
    ax.set_ylim(-1, 1)
    plt.axis('off')

    when_datetime = datetime.strptime(when, '%Y-%m-%d %H:%M:%S')
    ax.set_title(
        f"Observation Location: {location}\nTime: {when_datetime.strftime('%Y-%m-%d %H:%M')}",
        color='white',
        fontsize=10
    )

    return fig

def generate_star_map_png(location, when, chart_size=DEFAULT_CHART_SIZE, max_star_size=DEFAULT_MAX_STAR_SIZE, output_path=None):
    fig = generate_star_map(location, when, chart_size, max_star_size)
    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        when_datetime = datetime.strptime(when, '%Y-%m-%d %H:%M:%S')
        filename = f"{location}_{when_datetime.strftime('%Y%m%d_%H%M')}.png"
        output_path = OUTPUT_DIR / filename
    fig.savefig(output_path, format='png', dpi=1200, bbox_inches='tight')
    plt.close(fig)

def generate_star_map_gif(location, when, hours, step_minutes, chart_size=DEFAULT_CHART_SIZE, max_star_size=DEFAULT_MAX_STAR_SIZE):
    times = []
    start_dt = datetime.strptime(when, '%Y-%m-%d %H:%M:%S')
    total_frames = int((hours * 60) / step_minutes)

    for i in range(total_frames):
        times.append(start_dt + timedelta(minutes=i * step_minutes))

    images = []

    for t in times:
        when_str = t.strftime('%Y-%m-%d %H:%M:%S')
        fig = generate_star_map(location, when_str, chart_size, max_star_size)

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)

        img = imageio.v2.imread(buf)
        images.append(img)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    when_datetime = datetime.strptime(when, '%Y-%m-%d %H:%M:%S')
    filename = f"{location}_{when_datetime.strftime('%Y%m%d_%H%M')}.gif"
    gif_path = OUTPUT_DIR / filename

    imageio.mimsave(gif_path, images, duration=step_minutes * 60 / 10)