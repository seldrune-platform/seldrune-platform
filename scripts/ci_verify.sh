#!/usr/bin/env bash
set -euo pipefail

: "${SELDRUNE_DATABASE_URL:?SELDRUNE_DATABASE_URL is required}"
: "${SELDRUNE_CI_RELEASE_SHA:?SELDRUNE_CI_RELEASE_SHA is required}"

export SELDRUNE_MODEL_PROVIDER="${SELDRUNE_MODEL_PROVIDER:-mock}"
export SELDRUNE_MODEL_DEFAULT="${SELDRUNE_MODEL_DEFAULT:-mock-v1}"

python - <<'PY'
import os
import time

import psycopg

dsn = os.getenv(
    "SELDRUNE_CI_POSTGRES_DSN",
    "postgresql://postgres:postgres@127.0.0.1:5432/seldrune_ci",
)
for attempt in range(30):
    try:
        with psycopg.connect(dsn):
            print("PostgreSQL ready")
            break
    except Exception:
        if attempt == 29:
            raise
        time.sleep(1)
PY

ruff check .
pytest -q
alembic upgrade head

export SELDRUNE_ENVIRONMENT=production
export SELDRUNE_RELEASE_SHA="${SELDRUNE_CI_RELEASE_SHA}"
default_auth_secret="ci-production-secret-key-longer-than-thirty-two-characters"
export SELDRUNE_AUTH_SECRET_KEY="${SELDRUNE_AUTH_SECRET_KEY:-$default_auth_secret}"

uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 \
  > /tmp/seldrune-uvicorn.log 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' EXIT

python - <<'PY'
import hashlib
import hmac
import json
import os
import time

import httpx

url = "http://127.0.0.1:8000/api/v1/ready"
for attempt in range(30):
    try:
        response = httpx.get(url, timeout=2.0)
        response.raise_for_status()
        status = response.json()
        break
    except Exception:
        if attempt == 29:
            with open("/tmp/seldrune-uvicorn.log", encoding="utf-8") as handle:
                print(handle.read())
            raise
        time.sleep(1)

schema = status["checks"]["schema"]
assert status["ready"] is True
assert status["status"] == "ready"
assert status["environment"] == "production"
assert status["checks"]["database"]["status"] == "ok"
assert schema["status"] == "ok"
assert schema["schema_current"] is True
assert schema["current_revision"] == schema["expected_revision"]
assert status["checks"]["model_provider"]["status"] == "ok"
assert status["checks"]["model_provider"]["provider"] == "mock"
assert status["checks"]["model_provider"]["live_ai"] is False
assert status["release"] == {
    "sha": os.environ["SELDRUNE_CI_RELEASE_SHA"],
    "source": "seldrune",
}

receipt = {
    "version": "seldrune-ci-v1",
    "status": "success",
    "release_sha": os.environ["SELDRUNE_CI_RELEASE_SHA"],
    "checks": [
        "postgres-ready",
        "ruff",
        "pytest",
        "alembic-upgrade-head",
        "production-ready",
    ],
    "ready": status,
}
path = os.getenv(
    "SELDRUNE_CI_RECEIPT_PATH",
    "/tmp/seldrune-ci-receipt.json",
)
with open(path, "w", encoding="utf-8") as handle:
    json.dump(receipt, handle, indent=2, sort_keys=True)
    handle.write("\n")

print(f"SELDRUNE_CI_RECEIPT={path}")

signing_key = os.getenv("SELDRUNE_CI_RECEIPT_HMAC_KEY")
if signing_key:
    canonical = json.dumps(
        receipt,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    signature = hmac.new(
        signing_key.encode("utf-8"),
        canonical,
        hashlib.sha256,
    ).hexdigest()
    signature_value = f"sha256={signature}"
    signature_path = f"{path}.sig"
    with open(signature_path, "w", encoding="utf-8") as handle:
        handle.write(signature_value)
        handle.write("\n")
    print(f"SELDRUNE_CI_RECEIPT_SIGNATURE={signature_value}")
else:
    print("SELDRUNE_CI_RECEIPT_SIGNATURE=unsigned")
PY
