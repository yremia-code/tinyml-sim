import os, sys, requests, json
from dotenv import load_dotenv

load_dotenv()

TB_URL = os.getenv("TB_URL")
USER   = os.getenv("TB_USER")
PASS   = os.getenv("TB_PASS")

def login():
    r = requests.post(
        f"{TB_URL}/api/auth/login",
        json={"username": USER, "password": PASS},
        timeout=30
    )
    r.raise_for_status()
    return r.json()["token"]

def get_device_id(jwt, device_name):
    r = requests.get(
        f"{TB_URL}/api/tenant/devices",
        params={"pageSize": 100, "page": 0, "textSearch": device_name},
        headers={"X-Authorization": f"Bearer {jwt}"},
        timeout=30
    )
    r.raise_for_status()
    devices = r.json()["data"]
    for d in devices:
        if d["name"] == device_name:
            return d["id"]["id"]
    raise Exception(f"device '{device_name}' tidak ditemukan")

def push_shared(jwt, device_id, attrs):
    r = requests.post(
        f"{TB_URL}/api/plugins/telemetry/DEVICE/{device_id}/attributes/SHARED_SCOPE",
        headers={
            "X-Authorization": f"Bearer {jwt}",
            "Content-Type": "application/json"
        },
        json=attrs,
        timeout=30
    )
    r.raise_for_status()
    return r.status_code

if __name__ == "__main__":
    # args: device_name version model_url sha256
    device_name = sys.argv[1]
    version     = sys.argv[2]
    model_url   = sys.argv[3]
    sha256      = sys.argv[4]

    jwt = login()
    print(f"[tb_api] login OK")

    device_id = get_device_id(jwt, device_name)
    print(f"[tb_api] {device_name} -> {device_id}")

    code = push_shared(jwt, device_id, {
        "desired_version": version,
        "model_url": model_url,
        "model_sha256": sha256
    })
    print(f"[tb_api] push shared attr -> HTTP {code}")
