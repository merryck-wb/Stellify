import requests
import concurrent.futures
import time

API_URL = "http://localhost:8000"
USERNAME = "alice"
PASSWORD = "password123"

def get_token():
    resp = requests.post(
        f"{API_URL}/token",
        data={"username": USERNAME, "password": PASSWORD}
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

def hit_endpoint(token, endpoint="/video"):
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "location": "Brisbane, Australia",
        "when": "2025-01-01 00:00:00",
        "hours": 24,
        "step_minutes": 5
    }
    try:
        resp = requests.post(f"{API_URL}{endpoint}", headers=headers, json=payload)
        return resp.status_code
    except Exception as e:
        return str(e)

def run_load_test(duration=300, workers=10, endpoint="/video"):
    token = get_token()
    start = time.time()
    count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        while time.time() - start < duration:
            futures = [executor.submit(hit_endpoint, token, endpoint) for _ in range(workers)]
            for f in concurrent.futures.as_completed(futures):
                count += 1
                status = f.result()
                print(f"Request {count}: {status}")

if __name__ == "__main__":
    run_load_test(duration=300, workers=10, endpoint="/video")
