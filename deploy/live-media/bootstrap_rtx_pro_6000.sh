#!/usr/bin/env bash
set -euo pipefail

echo "== Seldrune RTX PRO 6000 worker bootstrap =="
nvidia-smi

cd "${SELDRUNE_ROOT:-/workspace/seldrune}"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"

python - <<'PY'
from services.live_media.gpu_backend_runtime import detect_gpu_backends
from services.live_media.readiness import check_readiness

gpu = detect_gpu_backends()
ready = check_readiness()
print("GPU backend:", gpu)
print("Live-media readiness:", ready)
if not gpu.cuda_available:
    raise SystemExit("CUDA backend is not available")
print("CUDA WORKER CHECK: PASS")
PY

echo "Bootstrap complete. No model weights are downloaded by this script."
