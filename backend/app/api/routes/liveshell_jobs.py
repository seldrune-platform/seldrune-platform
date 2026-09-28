"""Mobile, authenticated FaceFusion video-job API backed by a private worker token."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.app.api.dependencies import require_org_permission
from backend.app.api.routes.liveshell_mobile import _gateway_configuration
from backend.app.core.rbac import Permission
from backend.app.models.membership import Membership

WEB_ROOT = Path(__file__).resolve().parents[2] / "web"
page_router = APIRouter(tags=["liveshell-face-swap-mobile"])
api_router = APIRouter(prefix="/organizations", tags=["liveshell-video-jobs"])
live_run_dependency = require_org_permission(Permission.AGENTS_RUN)
LiveRunDep = Annotated[Membership, Depends(live_run_dependency)]
MAX_FACE_BYTES = 15 * 1024 * 1024
MAX_VIDEO_BYTES = 75 * 1024 * 1024
MAX_OUTPUT_BYTES = 100 * 1024 * 1024


@page_router.get("/liveshell/faceswap/mobile", include_in_schema=False)
def liveshell_face_swap_mobile_page() -> Response:
    return Response(
        content=(WEB_ROOT / "liveshell-face-swap-mobile.html").read_text(encoding="utf-8"),
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


class WorkerJobReceipt(BaseModel):
    model_config = ConfigDict(extra="ignore")

    job_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    status: Literal["queued"]
    synthetic_media_indicator_enabled: bool
    model: Literal["ghost_1_256"]
    model_license: Literal["Apache-2.0"]


class WorkerJobStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    job_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    status: Literal["queued", "processing", "completed", "failed"]
    error: str | None = None
    synthetic_media_indicator_enabled: bool
    model: Literal["ghost_1_256"]
    model_license: Literal["Apache-2.0"]
    output_width: int | None = Field(default=None, ge=1, le=7680)
    output_height: int | None = Field(default=None, ge=1, le=4320)
    output_fps: float | None = Field(default=None, ge=1, le=120)
    audio_sample_rate_hz: int | None = Field(default=None, ge=1, le=192_000)
    duration_seconds: float | None = Field(default=None, ge=0, le=3600)
    actual_accelerator_profile: Literal["rtx-4090"] | None = None
    audio_action: str | None = Field(default=None, max_length=160)


class WorkerReadiness(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["ready", "not_ready"]
    engine: Literal["facefusion"]
    accelerator: str | None = Field(default=None, max_length=120)
    synthetic_watermark: bool
    audio_sample_rate_hz: int
    voice_conversion: bool


def _readiness_url(base_url: str) -> str:
    return f"{base_url}/health"


def _job_url(base_url: str, job_id: str, *, download: bool = False) -> str:
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise HTTPException(status_code=404, detail="Face-swap job not found.")
    suffix = "/download" if download else ""
    return f"{base_url}/v1/jobs/{quote(job_id, safe='')}{suffix}"


def _worker_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _read_file(upload: UploadFile, limit: int, label: str) -> bytes:
    # UploadFile is deliberately read in the async route, with a bounded size.
    data = await upload.read(limit + 1)
    if not data:
        raise HTTPException(status_code=422, detail=f"The {label} file is empty.")
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"The {label} file is too large.")
    return data


async def _worker_error(response: httpx.Response, *, operation: str) -> None:
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Face-swap job not found.")
    if response.status_code == 409:
        raise HTTPException(status_code=409, detail="The face-swap job is not complete.")
    if response.status_code == 413:
        raise HTTPException(status_code=413, detail="The worker rejected an oversized media file.")
    if response.status_code == 422:
        raise HTTPException(status_code=422, detail="The worker rejected the media or consent fields.")
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"The FaceSwap worker could not {operation} the job.",
    )


@api_router.get("/{organization_id}/liveshift/video-jobs/readiness")
async def liveshell_video_job_readiness(
    organization_id: UUID,
    _membership: LiveRunDep,
) -> dict[str, object]:
    try:
        base_url, token = _gateway_configuration()
    except HTTPException:
        return {
            "worker_configured": False,
            "worker_ready": False,
            "video_target": "preserve uploaded video dimensions, up to 1080p",
            "audio_sample_rate_hz": 48_000,
            "voice_conversion": False,
        }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=3.0), follow_redirects=False) as client:
            response = await client.get(_readiness_url(base_url), headers=_worker_headers(token))
    except httpx.RequestError:
        return {
            "worker_configured": True,
            "worker_ready": False,
            "video_target": "preserve uploaded video dimensions, up to 1080p",
            "audio_sample_rate_hz": 48_000,
            "voice_conversion": False,
        }

    if response.status_code != 200:
        return {
            "worker_configured": True,
            "worker_ready": False,
            "video_target": "preserve uploaded video dimensions, up to 1080p",
            "audio_sample_rate_hz": 48_000,
            "voice_conversion": False,
        }
    try:
        worker = WorkerReadiness.model_validate(response.json())
    except (ValueError, ValidationError):
        worker = None
    return {
        "worker_configured": True,
        "worker_ready": bool(worker and worker.status == "ready" and worker.synthetic_watermark),
        "accelerator": worker.accelerator if worker else None,
        "video_target": "preserve uploaded video dimensions, up to 1080p",
        "audio_sample_rate_hz": worker.audio_sample_rate_hz if worker else 48_000,
        "voice_conversion": False,
        "note": "The source audio is retained; no voice conversion model is configured.",
    }


@api_router.post("/{organization_id}/liveshift/video-jobs", status_code=202)
async def create_liveshell_video_job(
    organization_id: UUID,
    membership: LiveRunDep,
    source_face: Annotated[UploadFile, File()],
    target_video: Annotated[UploadFile, File()],
    consent_confirmed: Annotated[bool, Form()],
    synthetic_media_indicator_enabled: Annotated[bool, Form()],
) -> dict[str, object]:
    if not consent_confirmed:
        raise HTTPException(status_code=422, detail="Authorization to use this face is required.")
    if not synthetic_media_indicator_enabled:
        raise HTTPException(status_code=422, detail="The synthetic-media label must remain enabled.")
    face_suffix = (source_face.filename or "").rsplit(".", maxsplit=1)[-1].lower()
    video_suffix = (target_video.filename or "").rsplit(".", maxsplit=1)[-1].lower()
    if face_suffix not in {"jpg", "jpeg", "png", "webp"}:
        raise HTTPException(status_code=415, detail="Use a JPG, PNG, or WebP face image.")
    if video_suffix not in {"mp4", "mov", "m4v", "webm"}:
        raise HTTPException(status_code=415, detail="Use an MP4, MOV, M4V, or WebM video.")
    face_data = await _read_file(source_face, MAX_FACE_BYTES, "face image")
    video_data = await _read_file(target_video, MAX_VIDEO_BYTES, "video")
    base_url, token = _gateway_configuration()
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(90.0, connect=5.0),
            follow_redirects=False,
        ) as client:
            response = await client.post(
                f"{base_url}/v1/jobs",
                data={
                    "organization_id": str(organization_id),
                    "user_id": str(membership.user_id),
                    "consent_confirmed": "true",
                    "synthetic_media_indicator_enabled": "true",
                },
                files={
                    "source_face": (
                        source_face.filename or f"face.{face_suffix}",
                        face_data,
                        source_face.content_type or "application/octet-stream",
                    ),
                    "target_video": (
                        target_video.filename or f"video.{video_suffix}",
                        video_data,
                        target_video.content_type or "application/octet-stream",
                    ),
                },
                headers=_worker_headers(token),
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="The face-swap worker timed out while accepting the upload.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="The face-swap worker could not be reached.") from exc
    if response.status_code != 202:
        await _worker_error(response, operation="accept")
    try:
        receipt = WorkerJobReceipt.model_validate(response.json())
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=502, detail="The worker returned an invalid job receipt.") from exc
    if not receipt.synthetic_media_indicator_enabled:
        raise HTTPException(status_code=502, detail="The worker did not confirm the synthetic-media label.")
    return {
        "job_id": receipt.job_id,
        "status": receipt.status,
        "synthetic_media_indicator_enabled": True,
        "model": receipt.model,
        "model_license": receipt.model_license,
        "audio_action": "source audio retained and re-encoded to AAC at 48 kHz; no voice conversion",
    }


@api_router.get("/{organization_id}/liveshift/video-jobs/{job_id}")
async def get_liveshell_video_job(
    organization_id: UUID,
    job_id: str,
    membership: LiveRunDep,
) -> dict[str, object]:
    base_url, token = _gateway_configuration()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0), follow_redirects=False) as client:
            response = await client.get(
                _job_url(base_url, job_id),
                params={"organization_id": str(organization_id), "user_id": str(membership.user_id)},
                headers=_worker_headers(token),
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="The face-swap worker timed out while checking the job.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="The face-swap worker could not be reached.") from exc
    if response.status_code != 200:
        await _worker_error(response, operation="read")
    try:
        job = WorkerJobStatus.model_validate(response.json())
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=502, detail="The worker returned an invalid job status.") from exc
    if job.job_id != job_id:
        raise HTTPException(status_code=502, detail="The worker returned a different job.")
    return job.model_dump()


@api_router.get("/{organization_id}/liveshift/video-jobs/{job_id}/download")
async def download_liveshell_video_job(
    organization_id: UUID,
    job_id: str,
    membership: LiveRunDep,
) -> Response:
    base_url, token = _gateway_configuration()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=5.0), follow_redirects=False) as client:
            response = await client.get(
                _job_url(base_url, job_id, download=True),
                params={"organization_id": str(organization_id), "user_id": str(membership.user_id)},
                headers=_worker_headers(token),
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="The face-swap worker timed out while preparing the download.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="The face-swap worker could not be reached.") from exc
    if response.status_code != 200:
        await _worker_error(response, operation="download")
    if len(response.content) > MAX_OUTPUT_BYTES:
        raise HTTPException(status_code=413, detail="The processed video is too large to return through this app.")
    return Response(
        content=response.content,
        media_type="video/mp4",
        headers={
            "Content-Disposition": 'attachment; filename="seldrune-face-swap-synthetic.mp4"',
            "Cache-Control": "no-store",
        },
    )


@api_router.delete("/{organization_id}/liveshift/video-jobs/{job_id}")
async def delete_liveshell_video_job(
    organization_id: UUID,
    job_id: str,
    membership: LiveRunDep,
) -> dict[str, bool]:
    base_url, token = _gateway_configuration()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0), follow_redirects=False) as client:
            response = await client.delete(
                _job_url(base_url, job_id),
                params={"organization_id": str(organization_id), "user_id": str(membership.user_id)},
                headers=_worker_headers(token),
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="The face-swap worker timed out while deleting the job.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="The face-swap worker could not be reached.") from exc
    if response.status_code != 200:
        await _worker_error(response, operation="delete")
    return {"deleted": True}
