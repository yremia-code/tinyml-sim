#!/bin/bash
set -e

VERSION=$1
DEVICE=$2
TB_URL=${TB_URL:?set TB_URL di env}

echo "== [1] Bikin model dummy versi $VERSION =="
mkdir -p artifacts/v$VERSION
echo "fake tflite model v$VERSION" > artifacts/v$VERSION/model.tflite
SHA=$(shasum -a 256 artifacts/v$VERSION/model.tflite | awk '{print $1}')
echo "sha256=$SHA"

echo "== [2] Commit & push artifact ke GitHub =="
git add artifacts/v$VERSION/model.tflite
git commit -m "model: v$VERSION" || echo "(nothing to commit)"
git push

echo "== [3] Push shared attribute ke ThingsBoard =="
MODEL_URL="${ARTIFACT_HOST}/v$VERSION/model.tflite"
python scripts/tb_api.py "$DEVICE" "$VERSION" "$MODEL_URL" "$SHA"

echo "== Selesai. Cek telemetry device di ThingsBoard. =="
