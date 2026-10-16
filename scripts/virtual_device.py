import paho.mqtt.client as mqtt
import json, os, hashlib, requests, time, threading, tempfile, random
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

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEST_SAMPLES = os.path.join(BASE, "data", "test_samples.npy")
TEST_LABELS  = os.path.join(BASE, "data", "test_labels.npy")

LABELS = ["no_irrigation", "light_irrigation", "heavy_irrigation"]

# Cache model yang sedang aktif biar nggak load ulang tiap inference
_active_model = {"path": None, "model": None}

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

def get_active_model():
    """Load model dari disk kalau belum di-cache."""
    if state["model_path"] is None:
        return None
    if _active_model["path"] == state["model_path"]:
        return _active_model["model"]
    try:
        m = joblib.load(state["model_path"])
        _active_model["path"] = state["model_path"]
        _active_model["model"] = m
        return m
    except Exception as e:
        print(f"[{NAME}] load model error: {e}")
        return None

def run_accuracy_test(model_path):
    """Test akurasi model di 300 sample test."""
    model = joblib.load(model_path)
    X = np.load(TEST_SAMPLES)
    y = np.load(TEST_LABELS)
    acc = float((model.predict(X) == y).mean())
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

        acc = run_accuracy_test(dest)
        print(f"[{NAME}] accuracy test OK, accuracy={acc:.4f}")

        state["current_version"] = desired
        state["model_path"] = dest
        state["accuracy"] = acc
        save_state(state)

        # Reset cache biar model baru di-load pas inference berikutnya
        _active_model["path"] = None
        _active_model["model"] = None

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

def inference_loop(client):
    """Loop utama: tiap 10 detik baca sensor, klasifikasi, kirim hasil."""
    time.sleep(5)  # tunggu device connect dulu
    while True:
        model = get_active_model()
        if model is None:
            print(f"[{NAME}] belum ada model, skip inference")
            time.sleep(10)
            continue

        # Simulasi baca sensor — kondisi random
        sensor = {
            "soil_moisture": round(random.uniform(15, 85), 1),
            "temperature":   round(random.uniform(20, 40), 1),
            "humidity":      round(random.uniform(30, 90), 1),
            "soil_ph":       round(random.uniform(5.0, 7.5), 2)
        }

        # Inference
        X = [[sensor["soil_moisture"], sensor["temperature"],
              sensor["humidity"], sensor["soil_ph"]]]
        pred = int(model.predict(X)[0])
        decision = LABELS[pred]

        # Kirim ke ThingsBoard
        payload = {
            **sensor,
            "decision": decision,
            "decision_code": pred,
            "model_version": state["current_version"],
            "ts": int(time.time() * 1000)
        }
        client.publish("v1/devices/me/telemetry", json.dumps(payload))
        print(f"[{NAME}] SENSOR: {sensor} -> KEPUTUSAN: {decision} (model v{state['current_version']})")

        time.sleep(10)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=NAME)
client.username_pw_set(TOKEN)
client.on_connect = on_connect
client.on_message = on_message
client.connect(TB_HOST, TB_PORT, 60)

threading.Thread(target=heartbeat, args=(client,), daemon=True).start()
threading.Thread(target=inference_loop, args=(client,), daemon=True).start()
client.loop_forever()
