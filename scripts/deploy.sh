#!/bin/bash
set -e

VERSION=$1
DEVICE=$2
TB_URL=${TB_URL:?set TB_URL di env}

MODEL_FILE="artifacts/v$VERSION/model.pkl"

if [ ! -f "$MODEL_FILE" ]; then
  echo "ERROR: $MODEL_FILE tidak ada."
  echo "Taruh model .pkl hasil Colab di path tersebut dulu."
  exit 1
fi

echo "== [1] Pakai model versi $VERSION =="
ls -lh "$MODEL_FILE"
SHA=$(sha256sum "$MODEL_FILE" | awk '{print $1}')
echo "sha256=$SHA"

echo "== [2] Commit & push artifact ke GitHub =="
git add "$MODEL_FILE"
git commit -m "model: v$VERSION" || echo "(nothing to commit)"
git push

echo "== [3] Push shared attribute ke ThingsBoard =="
MODEL_URL="${ARTIFACT_HOST}/v$VERSION/model.pkl"
python scripts/tb_api.py "$DEVICE" "$VERSION" "$MODEL_URL" "$SHA"

echo "== Selesai. Cek telemetry device di ThingsBoard. =="
