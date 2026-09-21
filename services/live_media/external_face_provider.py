"""External face-transformation provider adapter.

Keeps third-party inference behind a Seldrune-owned interface so providers can
be replaced without changing product-facing code. Use only with
authorized/consensual source and target media.
"""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Any
import httpx

class FaceProviderError(RuntimeError):
    pass

@dataclass(frozen=True)
class FaceSwapRequest:
    target_image: str
    source_face: str
    consent_confirmed: bool

class ReplicateFaceProvider:
    API = "https://api.replicate.com/v1/predictions"

    def __init__(self, token: str | None = None, version: str | None = None,
                 target_key: str | None = None, source_key: str | None = None) -> None:
        self.token = token or os.getenv("REPLICATE_API_TOKEN")
        self.version = version or os.getenv("SELDRUNE_FACE_REPLICATE_VERSION")
        self.target_key = target_key or os.getenv("SELDRUNE_FACE_TARGET_KEY", "input_image")
        self.source_key = source_key or os.getenv("SELDRUNE_FACE_SOURCE_KEY", "swap_image")
        if not self.token:
            raise FaceProviderError("REPLICATE_API_TOKEN is not configured")
        if not self.version:
            raise FaceProviderError("SELDRUNE_FACE_REPLICATE_VERSION is not configured")

    def create(self, request: FaceSwapRequest) -> dict[str, Any]:
        if not request.consent_confirmed:
            raise FaceProviderError("consent confirmation is required")
        payload = {"version": self.version, "input": {
            self.target_key: request.target_image,
            self.source_key: request.source_face,
        }}
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Prefer": "wait=60",
            "Cancel-After": "2m",
        }
        with httpx.Client(timeout=70.0) as client:
            response = client.post(self.API, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
        if result.get("status") == "failed":
            raise FaceProviderError(result.get("error") or "face provider failed")
        return result
