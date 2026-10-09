import paho.mqtt.client as mqtt
import json, os, hashlib, requests, time, threading, tempfile
from dotenv import load_dotenv

load_dotenv()

TB_HOST = os.getenv("TB_MQTT_HOST")
TB_PORT = int(os.getenv("TB_MQTT_PORT", "1883"))
NAME    = os.getenv("DEVICE_NAME")
TOKEN   = os.getenv("DEVICE_TOKEN")

TMP = tempfile.gettempdir()
STATE_FILE = os.path.join(TMP, f"{NAME}_state.json")

def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {"current_version": "1.0.0", "model_path": None}

def save_state(s):
    json.dump(s, open(STATE_FILE, "w"))

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def download(url, dest):
    r = requests.get(url, stream=True, timeout=30)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

state = load_state()

def publish_status(client, version, status, error=""):
    payload = {
        "current_model_version": version,
        "update_status": status,
        "last_error": error,
        "ts": int(time.time() * 1000)
    }
    client.publish("v1/devices/me/telemetry", json.dumps(payload))
    print(f"[{NAME}] telemetry: {payload}")

def handle_update(client, attrs):
    desired = attrs.get("desired_version")
    url     = attrs.get("model_url")
    sha     = attrs.get("model_sha256")

    if not desired or desired == state["current_version"]:
        return

    print(f"[{NAME}] update {state['current_version']} -> {desired}")
    dest = os.path.join(TMP, f"{NAME}_model_{desired}.tflite")
    try:
        download(url, dest)
        got = sha256_file(dest)
        if got != sha:
            raise Exception(f"checksum mismatch: {got} != {sha}")
        time.sleep(1)
        state["current_version"] = desired
        state["model_path"] = dest
        save_state(state)
        publish_status(client, desired, "success")
    except Exception as e:
        publish_status(client, state["current_version"], "failed", str(e))

def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"[{NAME}] connected rc={reason_code}")
    client.subscribe("v1/devices/me/attributes")
    publish_status(client, state["current_version"], "boot")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload)
        attrs = payload.get("shared", payload)
        handle_update(client, attrs)
    except Exception as e:
        print(f"[{NAME}] msg error: {e}")

def heartbeat(client):
    while True:
        publish_status(client, state["current_version"], "running")
        time.sleep(30)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=NAME)
client.username_pw_set(TOKEN)
client.on_connect = on_connect
client.on_message = on_message
client.connect(TB_HOST, TB_PORT, 60)

threading.Thread(target=heartbeat, args=(client,), daemon=True).start()
client.loop_forever()
