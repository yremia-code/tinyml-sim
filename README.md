# TinyML CI/CD Simulation with ThingsBoard

Simulasi pipeline deployment model TinyML ke edge device menggunakan ThingsBoard sebagai control plane, dengan virtual device Python sebagai proxy untuk perangkat edge yang belum tersedia.

## Latar Belakang

Model TinyML (TFLite, Edge Impulse, dsb) yang berjalan di perangkat edge perlu di-update secara berkala — misal karena akurasi turun, ada bug, atau ada model baru yang lebih baik. Update manual (cabut SD card, flash ulang) tidak scalable untuk fleet device yang banyak.

Repo ini mengeksplorasi mekanisme **over-the-air model update** dengan ThingsBoard sebagai orchestrator, disimulasikan dengan virtual device.

## Arsitektur

    ┌─────────────┐   push    ┌──────────────┐
    │   Colab /   │─────────▶│    GitHub    │
    │  Notebook   │ artifacts │    (raw)     │
    └─────────────┘           └──────┬───────┘
                                     │ HTTP GET
                                     ▼
    ┌─────────────┐ shared attr ┌──────────────┐
    │  deploy.sh  │───────────▶│ ThingsBoard  │
    │   (CI/CD)   │             │   (kampus)   │
    └─────────────┘             └──────┬───────┘
                                     │ MQTT
                                     ▼
                              ┌──────────────┐
                              │   Virtual    │
                              │    Device    │
                              │   (Python)   │
                              └──────────────┘

**Alur:**
1. `deploy.sh` membuat artifact model baru (simulasi export dari Colab).
2. Artifact di-push ke GitHub.
3. `deploy.sh` mengirim **shared attribute** ke ThingsBoard: `desired_version`, `model_url`, `model_sha256`.
4. Virtual device yang subscribe ke topic attributes menerima update.
5. Device download model, verifikasi SHA256, "load" model, dan lapor status balik ke ThingsBoard via telemetry.

## Konsep Kunci

* **Desired State vs Reported State**
  * `desired_version` (shared attribute) = versi yang diinginkan server.
  * `current_model_version` (telemetry) = versi aktual di device.
  * Selisih keduanya = sinyal untuk device melakukan update.
* **Idempotent Update**
  Mengirim attribute yang sama berkali-kali tidak menyebabkan update berulang — device hanya update kalau `desired != current`.
* **Checksum Verification**
  Setiap model diverifikasi dengan SHA256 sebelum diaktifkan. Ini mencegah device memuat model korup atau termodifikasi.
* **Canary Rollout**
  Deploy ke satu device dulu. Kalau sukses, baru rollout ke sisanya.
* **Rollback**
  Deploy versi lama = rollback. Device otomatis turun versi.

## Struktur Repo

    tinyml-sim/
    ├── artifacts/             # model dummy per versi
    │   └── v1.2.1/model.tflite
    ├── scripts/
    │   ├── virtual_device.py  # simulasi edge device
    │   ├── deploy.sh          # simulasi pipeline CI/CD
    │   └── tb_api.py          # helper ThingsBoard REST API
    ├── .env                   # kredensial (TIDAK di-commit)
    ├── .gitignore
    └── README.md

## Setup

### 1. Requirements
* Python 3.9+
* Git
* Akses ThingsBoard (role Tenant)
* Port MQTT terbuka (1883 atau 8883)

### 2. Install dependencies
    pip install paho-mqtt requests python-dotenv

### 3. Bikin device di ThingsBoard
1. Login sebagai Tenant.
2. Ke menu **Devices** → **Add new device** → buat `virtual-esp32-01`, `virtual-esp32-02`, `virtual-esp32-03`.
3. Copy access token masing-masing.

### 4. Konfigurasi .env
Buat file `.env` dan isi dengan:
    TB_URL=https://thingsboard.kampus.ac.id
    TB_MQTT_HOST=thingsboard.kampus.ac.id
    TB_MQTT_PORT=1883
    
    TB_USER=email_tenant
    TB_PASS=password_tenant
    
    DEVICE_01=virtual-esp32-01
    DEVICE_02=virtual-esp32-02
    DEVICE_03=virtual-esp32-03
    
    TOKEN_01=...
    TOKEN_02=...
    TOKEN_03=...
    
    ARTIFACT_HOST=https://raw.githubusercontent.com/USER/tinyml-sim/main/artifacts

## Cara Pakai

**Jalankan virtual device (3 terminal terpisah)**
    set -a; source .env; set +a
    DEVICE_NAME=virtual-esp32-01 DEVICE_TOKEN=$TOKEN_01 python scripts/virtual_device.py

**Deploy model baru**
    set -a; source .env; set +a
    ./scripts/deploy.sh 1.2.1 $DEVICE_01

**Rollback**
    ./scripts/deploy.sh 1.2.0 $DEVICE_01

## Skenario Demo

| Skenario | Command |
| --- | --- |
| **Canary** | `./scripts/deploy.sh 1.3.0 $DEVICE_01` |
| **Full rollout** | `./scripts/deploy.sh 1.3.0 $DEVICE_02 && ./scripts/deploy.sh 1.3.0 $DEVICE_03` |
| **Failure test** | kirim sha salah via `tb_api.py` |
| **Rollback** | `./scripts/deploy.sh 1.2.1 $DEVICE_01` |

## Batasan Simulasi
* Virtual device, bukan MCU asli (ESP32/STM32).
* Model hanya file dummy — belum ada inference TFLite Micro.
* Belum ada signing (Ed25519) untuk model.
* Belum ada A/B partition di device.
* Belum ada power-loss test saat update.

## Next Step
* Ganti virtual device dengan ESP32 asli + TFLite Micro.
* Tambah signing model untuk verifikasi origin.
* Bikin OTA firmware (bukan hanya model).
* Integrasi dengan MLflow/DVC sebagai model registry.
* Rule Engine ThingsBoard untuk auto-rollback saat update gagal.

## Referensi
* ThingsBoard Documentation
* TinyMLOps: Operational Challenges for Widespread Edge AI Deployment
* MLOps for Edge Devices
