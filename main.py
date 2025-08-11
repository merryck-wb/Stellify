import matplotlib.pyplot as plt
from skyfield.api import load, Star, wgs84
from skyfield.data import hipparcos
from skyfield.projections import build_stereographic_projection
from geopy import Nominatim
from datetime import datetime
from pytz import timezone, utc
import requests
import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
CACHE_FILE = BASE_DIR / "location_cache.json"

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

def generate_star_map(location, when, chart_size, max_star_size):
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
    plt.title(
        f"Observation Location: {location}, Time: {when_datetime.strftime('%Y-%m-%d %H:%M')}", 
        loc='right',
        color = 'white',
        fontsize=10)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{location}_{when_datetime.strftime('%Y%m%d_%H%M')}.png"
    save_path = OUTPUT_DIR / filename
    plt.savefig(save_path, format='png', dpi=1200, bbox_inches='tight')