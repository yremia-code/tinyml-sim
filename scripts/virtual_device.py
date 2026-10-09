import paho.mqtt.client as mqtt
import json, os, hashlib, requests, time, threading, tempfile
import numpy as np
import joblib
from dotenv import load_dotenv

load_dotenv()

TB_HOST = os.getenv("TB_MQTT_HOST")
TB_PORT = int(os.getenv("TB_MQTT_PORT", "1883"))
NAME    = os.getenv("DEVICE_NAME")
TOKEN   = os.getenv("DEVICE_TOKEN")

TMP = tempfile.gettempdir()
STATE_FILE = os.path.join(TMP, f"{NAME}_state.json")

# Path test set (relatif ke root repo)
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEST_SAMPLES = os.path.join(BASE, "data", "test_samples.npy")
TEST_LABELS  = os.path.join(BASE, "data", "test_labels.npy")

def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {"current_version": "0.0.0", "model_path": None, "accuracy": None}

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

def run_inference(model_path):
    """Load model kNN (.pkl), run inference di 30 test sample, return accuracy."""
    model = joblib.load(model_path)
    X = np.load(TEST_SAMPLES)
    y = np.load(TEST_LABELS)

    preds = model.predict(X)
    acc = float((preds == y).mean())
    return acc

state = load_state()

def publish_status(client, version, status, error="", accuracy=None):
    payload = {
        "current_model_version": version,
        "update_status": status,
        "last_error": error,
        "test_accuracy": accuracy if accuracy is not None else state.get("accuracy"),
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
    dest = os.path.join(TMP, f"{NAME}_model_{desired}.pkl")
    try:
        download(url, dest)
        got = sha256_file(dest)
        if got != sha:
            raise Exception(f"checksum mismatch: {got} != {sha}")

        acc = run_inference(dest)
        print(f"[{NAME}] inference OK, accuracy={acc:.4f}")

        state["current_version"] = desired
        state["model_path"] = dest
        state["accuracy"] = acc
        save_state(state)

        publish_status(client, desired, "success", accuracy=acc)
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
