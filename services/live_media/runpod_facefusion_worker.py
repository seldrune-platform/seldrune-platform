"""Authenticated asynchronous FaceFusion worker for RunPod RTX GPUs.

The worker handles mobile video jobs over HTTPS. It preserves the source audio,
re-encodes it to AAC at 48 kHz, and burns a synthetic-media label into the video.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import os
import shutil
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

MAX_FACE_BYTES = 15 * 1024 * 1024
MAX_VIDEO_BYTES = 75 * 1024 * 1024
MAX_VIDEO_SECONDS = 30.0
MAX_VIDEO_PIXELS = 1920 * 1080
MAX_VIDEO_DIMENSION = 1920
OUTPUT_VIDEO_FPS = 30
MAX_ACTIVE_JOBS = 2
JOB_TTL_SECONDS = 3600
JOB_TIMEOUT_SECONDS = 1800
DATA_ROOT = Path(os.getenv("SELDRUNE_RUNPOD_JOB_DIR", "/workspace/seldrune-faceswap-jobs"))
FACEFUSION_ROOT = Path(os.getenv("FACEFUSION_ROOT", "/opt/facefusion"))
JOBS: dict[str, dict[str, object]] = {}
GPU_SLOT = asyncio.Semaphore(1)


async def _cleanup_expired_jobs() -> None:
    while True:
        await asyncio.sleep(60)
        _prune_expired_jobs()


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    cleanup_task = asyncio.create_task(_cleanup_expired_jobs())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Seldrune RunPod FaceSwap Worker",
    docs_url=None,
    redoc_url=None,
    lifespan=_lifespan,
)


def _authorize(authorization: str | None) -> None:
    expected_token = os.getenv("SELDRUNE_FACESWAP_WORKER_TOKEN", "").strip()
    if not expected_token:
        raise HTTPException(status_code=503, detail="Worker authentication is not configured.")
    expected = f"Bearer {expected_token}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Worker authentication failed.")


def _owner_values(organization_id: str, user_id: str) -> tuple[str, str]:
    try:
        return str(UUID(organization_id)), str(UUID(user_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid job owner.") from exc


def _validate_extension(filename: str | None, allowed: set[str], label: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(status_code=415, detail=f"Unsupported {label} file type.")
    return suffix


async def _read_limited(upload: UploadFile, limit: int, label: str) -> bytes:
    data = await upload.read(limit + 1)
    if not data:
        raise HTTPException(status_code=422, detail=f"The {label} file is empty.")
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"The {label} file is too large.")
    return data


def build_facefusion_command(
    source_path: Path, target_path: Path, output_path: Path
) -> list[str]:
    """Build a fixed FaceFusion invocation without shell interpretation."""
    return [
        sys.executable,
        "facefusion.py",
        "headless-run",
        "--processors",
        "face_swapper",
        "--face-swapper-model",
        "ghost_1_256",
        "--face-selector-mode",
        "one",
        "--execution-providers",
        "cuda",
        "--execution-device-ids",
        "0",
        "--video-memory-strategy",
        "strict",
        "--source-paths",
        str(source_path),
        "--target-path",
        str(target_path),
        "--output-path",
        str(output_path),
        "--output-video-encoder",
        "libx264",
        "--output-video-preset",
        "veryfast",
        "--output-video-quality",
        "85",
        "--output-audio-encoder",
        "aac",
        "--output-audio-quality",
        "92",
    ]


def _synthetic_output_command(
    source_path: Path,
    output_path: Path,
    source_width: int,
    source_height: int,
) -> list[str]:
    target_width, target_height = output_canvas_dimensions(source_width, source_height)
    drawtext = (
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        "text='AI-SYNTHETIC':x=18:y=18:fontcolor=white:fontsize=26:"
        "box=1:boxcolor=black@0.65:boxborderw=8"
    )
    video_filter = (
        f"scale={target_width}:{target_height}:"
        "force_original_aspect_ratio=decrease:force_divisible_by=2,"
        f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"setsar=1,fps={OUTPUT_VIDEO_FPS},{drawtext}"
    )
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-vf",
        video_filter,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-r",
        str(OUTPUT_VIDEO_FPS),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

async def _run_command(command: list[str], *, cwd: Path, timeout: float) -> bytes:
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise RuntimeError("Media processing exceeded its time limit.") from None
    if process.returncode != 0:
        raise RuntimeError("Media processing failed.")
    return output


async def _probe_video(path: Path) -> dict[str, object]:
    output = await _run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height,r_frame_rate,avg_frame_rate,sample_rate",
            "-of",
            "json",
            str(path),
        ],
        cwd=path.parent,
        timeout=20,
    )
    try:
        return json.loads(output)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("The video metadata could not be read.") from exc


async def _runtime_ready() -> tuple[bool, str | None]:
    if not FACEFUSION_ROOT.is_dir():
        return False, None
    try:
        gpu = await _run_command(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            cwd=Path("/tmp"),
            timeout=10,
        )
        await _run_command(
            [
                sys.executable,
                "-c",
                "import onnxruntime as ort; "
                "assert 'CUDAExecutionProvider' in ort.get_available_providers()",
            ],
            cwd=FACEFUSION_ROOT,
            timeout=10,
        )
    except (OSError, RuntimeError):
        return False, None
    gpu_name = gpu.decode("utf-8", errors="ignore").strip().splitlines()
    return bool(gpu_name), gpu_name[0] if gpu_name else None


def _fraction(value: object) -> float | None:
    if not isinstance(value, str) or "/" not in value:
        return None
    try:
        numerator, denominator = value.split("/", maxsplit=1)
        return float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        return None


def output_canvas_dimensions(source_width: int, source_height: int) -> tuple[int, int]:
    if source_width <= 0 or source_height <= 0:
        raise ValueError("The source video dimensions are invalid.")
    if source_width >= source_height:
        return 1920, 1080
    return 1080, 1920


def meets_output_target(
    width: int,
    height: int,
    frame_rate: float | None,
    source_width: int,
    source_height: int,
) -> bool:
    expected_dimensions = output_canvas_dimensions(source_width, source_height)
    return (
        (width, height) == expected_dimensions
        and frame_rate is not None
        and abs(frame_rate - OUTPUT_VIDEO_FPS) < 0.001
    )


def supports_video_dimensions(width: int, height: int) -> bool:
    return (
        width > 0
        and height > 0
        and max(width, height) <= MAX_VIDEO_DIMENSION
        and width * height <= MAX_VIDEO_PIXELS
    )


async def _process_job(job_id: str) -> None:
    job = JOBS.get(job_id)
    if not job:
        return
    async with GPU_SLOT:
        job["status"] = "processing"
        job["updated_at"] = time.time()
        work_dir = Path(str(job["work_dir"]))
        source = Path(str(job["source_path"]))
        target = Path(str(job["target_path"]))
        raw_output = work_dir / "faceswapped.mp4"
        labeled_output = work_dir / "seldrune-synthetic-output.mp4"
        try:
            if not FACEFUSION_ROOT.is_dir():
                raise RuntimeError("The FaceFusion runtime is not installed.")
            await _run_command(
                build_facefusion_command(source, target, raw_output),
                cwd=FACEFUSION_ROOT,
                timeout=JOB_TIMEOUT_SECONDS,
            )
            if not raw_output.is_file() or raw_output.stat().st_size == 0:
                raise RuntimeError("FaceFusion produced no output video.")
            raw_metadata = await _probe_video(raw_output)
            raw_streams = raw_metadata.get("streams", [])
            raw_video_stream = next(
                (item for item in raw_streams if item.get("codec_type") == "video"), None
            )
            if not raw_video_stream:
                raise RuntimeError("FaceFusion produced no video stream.")
            source_width = int(raw_video_stream.get("width", 0))
            source_height = int(raw_video_stream.get("height", 0))
            if source_width <= 0 or source_height <= 0:
                raise RuntimeError("FaceFusion produced invalid video dimensions.")
            await _run_command(
                _synthetic_output_command(
                    raw_output, labeled_output, source_width, source_height
                ),
                cwd=work_dir,
                timeout=JOB_TIMEOUT_SECONDS,
            )
            if not labeled_output.is_file() or labeled_output.stat().st_size == 0:
                raise RuntimeError("The labeled output video was not created.")
            metadata = await _probe_video(labeled_output)
            streams = metadata.get("streams", [])
            video_stream = next(
                (item for item in streams if item.get("codec_type") == "video"), None
            )
            audio_stream = next(
                (item for item in streams if item.get("codec_type") == "audio"), None
            )
            if not video_stream:
                raise RuntimeError("The output video stream is missing.")
            output_width = int(video_stream.get("width", 0))
            output_height = int(video_stream.get("height", 0))
            output_fps = (
                _fraction(video_stream.get("avg_frame_rate"))
                or _fraction(video_stream.get("r_frame_rate"))
            )
            if not meets_output_target(
                output_width,
                output_height,
                output_fps,
                source_width,
                source_height,
            ):
                raise RuntimeError("The output video does not meet the 1080p/30 fps target.")
            duration = float(metadata.get("format", {}).get("duration", 0.0))
            actual_accelerator = None
            try:
                gpu = await _run_command(
                    ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                    cwd=work_dir,
                    timeout=10,
                )
                if "4090" in gpu.decode("utf-8", errors="ignore"):
                    actual_accelerator = "rtx-4090"
            except (OSError, RuntimeError):
                pass
            job["output_path"] = str(labeled_output)
            job["output_width"] = output_width
            job["output_height"] = output_height
            job["output_fps"] = output_fps
            job["audio_sample_rate_hz"] = (
                int(audio_stream["sample_rate"])
                if audio_stream and audio_stream.get("sample_rate")
                else None
            )
            job["duration_seconds"] = duration
            job["actual_accelerator_profile"] = actual_accelerator
            job["audio_action"] = "original audio re-encoded to AAC at 48 kHz; no voice conversion"
            job["status"] = "completed"
        except (OSError, RuntimeError, ValueError, KeyError, TypeError):
            job["status"] = "failed"
            job["error"] = "The worker could not complete this face-swap job."
        finally:
            job["updated_at"] = time.time()
            for upload_path in (source, target, raw_output):
                try:
                    upload_path.unlink(missing_ok=True)
                except OSError:
                    pass


def _check_owner(job: dict[str, object], organization_id: str, user_id: str) -> None:
    org_id, owner_id = _owner_values(organization_id, user_id)
    if job.get("organization_id") != org_id or job.get("user_id") != owner_id:
        raise HTTPException(status_code=404, detail="Face-swap job not found.")


def _prune_expired_jobs() -> None:
    cutoff = time.time() - JOB_TTL_SECONDS
    for job_id, job in list(JOBS.items()):
        active = job.get("status") in {"queued", "processing"}
        if float(job.get("updated_at", 0)) >= cutoff or active:
            continue
        work_dir = Path(str(job.get("work_dir", "")))
        if work_dir.is_dir():
            shutil.rmtree(work_dir, ignore_errors=True)
        JOBS.pop(job_id, None)


@app.get("/health")
async def health() -> dict[str, object]:
    ready, gpu_name = await _runtime_ready()
    return {
        "status": "ready" if ready else "not_ready",
        "engine": "facefusion",
        "accelerator": gpu_name,
        "synthetic_watermark": True,
        "audio_sample_rate_hz": 48000,
        "voice_conversion": False,
    }


@app.post("/v1/jobs", status_code=202)
async def create_job(
    source_face: Annotated[UploadFile, File()],
    target_video: Annotated[UploadFile, File()],
    organization_id: Annotated[str, Form()],
    user_id: Annotated[str, Form()],
    consent_confirmed: Annotated[bool, Form()],
    synthetic_media_indicator_enabled: Annotated[bool, Form()],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _authorize(authorization)
    org_id, owner_id = _owner_values(organization_id, user_id)
    if not consent_confirmed or not synthetic_media_indicator_enabled:
        raise HTTPException(
            status_code=422,
            detail="Authorization and the synthetic label are required.",
        )
    active_job_count = sum(
        job.get("status") in {"queued", "processing"}
        for job in JOBS.values()
    )
    if active_job_count >= MAX_ACTIVE_JOBS:
        raise HTTPException(
            status_code=429,
            detail="The GPU queue is full. Try again after a job completes.",
        )
    ready, _gpu_name = await _runtime_ready()
    if not ready:
        raise HTTPException(status_code=503, detail="The FaceSwap GPU worker is not ready.")
    face_suffix = _validate_extension(
        source_face.filename, {".jpg", ".jpeg", ".png", ".webp"}, "face image"
    )
    video_suffix = _validate_extension(
        target_video.filename, {".mp4", ".mov", ".m4v", ".webm"}, "video"
    )
    face_data = await _read_limited(source_face, MAX_FACE_BYTES, "face image")
    video_data = await _read_limited(target_video, MAX_VIDEO_BYTES, "video")
    _prune_expired_jobs()
    job_id = uuid4().hex
    work_dir = DATA_ROOT / job_id
    work_dir.mkdir(parents=True, exist_ok=False)
    face_path = work_dir / f"authorized-face{face_suffix}"
    video_path = work_dir / f"target-video{video_suffix}"
    face_path.write_bytes(face_data)
    video_path.write_bytes(video_data)
    try:
        metadata = await _probe_video(video_path)
        format_info = metadata.get("format", {})
        streams = metadata.get("streams", [])
        video_stream = next(
            (item for item in streams if item.get("codec_type") == "video"), None
        )
        duration = float(format_info.get("duration", 0.0))
        if not video_stream or duration <= 0 or duration > MAX_VIDEO_SECONDS:
            raise ValueError("unsupported video duration or stream")
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        if not supports_video_dimensions(width, height):
            raise ValueError("video exceeds the supported 1080p input target")
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(
            status_code=422,
            detail="Use a readable video up to 30 seconds and 1080p.",
        ) from exc
    now = time.time()
    JOBS[job_id] = {
        "job_id": job_id,
        "organization_id": org_id,
        "user_id": owner_id,
        "status": "queued",
        "work_dir": str(work_dir),
        "source_path": str(face_path),
        "target_path": str(video_path),
        "created_at": now,
        "updated_at": now,
        "synthetic_media_indicator_enabled": True,
        "model": "ghost_1_256",
        "model_license": "Apache-2.0",
    }
    asyncio.create_task(_process_job(job_id))
    return {
        "job_id": job_id,
        "status": "queued",
        "synthetic_media_indicator_enabled": True,
        "model": "ghost_1_256",
        "model_license": "Apache-2.0",
    }


@app.get("/v1/jobs/{job_id}")
async def get_job(
    job_id: str,
    organization_id: str,
    user_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _authorize(authorization)
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Face-swap job not found.")
    _check_owner(job, organization_id, user_id)
    return {
        key: job[key]
        for key in (
            "job_id",
            "status",
            "error",
            "synthetic_media_indicator_enabled",
            "model",
            "model_license",
            "output_width",
            "output_height",
            "output_fps",
            "audio_sample_rate_hz",
            "duration_seconds",
            "actual_accelerator_profile",
            "audio_action",
        )
        if key in job
    }


@app.get("/v1/jobs/{job_id}/download")
async def download_job(
    job_id: str,
    organization_id: str,
    user_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> FileResponse:
    _authorize(authorization)
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Face-swap job not found.")
    _check_owner(job, organization_id, user_id)
    if job.get("status") != "completed" or not job.get("output_path"):
        raise HTTPException(status_code=409, detail="The face-swap job is not complete.")
    return FileResponse(
        str(job["output_path"]),
        media_type="video/mp4",
        filename="seldrune-face-swap-synthetic.mp4",
        headers={"Cache-Control": "no-store"},
    )


@app.delete("/v1/jobs/{job_id}")
async def delete_job(
    job_id: str,
    organization_id: str,
    user_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, bool]:
    _authorize(authorization)
    job = JOBS.get(job_id)
    if not job:
        return {"deleted": True}
    _check_owner(job, organization_id, user_id)
    if job.get("status") in {"queued", "processing"}:
        raise HTTPException(status_code=409, detail="A running job cannot be deleted yet.")
    shutil.rmtree(Path(str(job["work_dir"])), ignore_errors=True)
    JOBS.pop(job_id, None)
    return {"deleted": True}
