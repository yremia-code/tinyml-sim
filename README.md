# TinyML CI/CD Simulation with ThingsBoard

Simulasi deployment model TinyML ke edge device menggunakan ThingsBoard
sebagai control plane. Device disimulasikan dengan Python (virtual device).

## Komponen
- Virtual device: Python + MQTT
- Control plane: ThingsBoard (server kampus)
- Artifact store: GitHub raw / HTTP server lokal

## Struktur
- `scripts/virtual_device.py` — simulasi device
- `scripts/deploy.sh` — simulasi pipeline deploy
- `artifacts/` — model dummy per versi
