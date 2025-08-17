import requests
import concurrent.futures
import time

API_URL = "http://localhost:8000"
USERNAME = "alice"
PASSWORD = "password123"

def get_token():
    """Authenticate and return a bearer token."""
    resp = requests.post(
        f"{API_URL}/token",
        data={"username": USERNAME, "password": PASSWORD}
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

def hit_endpoint(session, token, endpoint="/video"):
    """Send one request to the API endpoint."""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "location": "Sydney, Australia",
        "when": "2025-01-01 00:00:00",
        "hours": 24,
        "step_minutes": 5
    }
    try:
        resp = session.post(f"{API_URL}{endpoint}", headers=headers, params=payload)
        return resp.status_code
    except Exception as e:
        return str(e)

def run_load_test(duration=300, workers=3, endpoint="/video"):
    token = get_token()
    start = time.time()
    count = 0

    with requests.Session() as session:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            while time.time() - start < duration:
                futures = [executor.submit(hit_endpoint, session, token, endpoint) for _ in range(workers)]
                for f in concurrent.futures.as_completed(futures):
                    count += 1
                    status = f.result()
                    print(f"Request {count}: {status}")

if __name__ == "__main__":
    run_load_test()
