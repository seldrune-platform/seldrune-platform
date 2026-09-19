"""Executable entry point for admitted Seldrune Face GPU training jobs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.live_media.face_gpu_execution import GpuTrainingExecution


def load_execution_manifest(path: Path) -> GpuTrainingExecution:
    payload = json.loads(path.read_text(encoding="utf-8"))
    execution = GpuTrainingExecution(
        job_id=payload["job_id"],
        model_version=payload["model_version"],
        accelerator=payload["accelerator"],
        dataset_manifest_sha256=payload["dataset_manifest_sha256"],
        max_steps=int(payload["max_steps"]),
        checkpoint_every=int(payload["checkpoint_every"]),
        precision=payload["precision"],
        output_dir=payload["output_dir"],
    )
    execution.validate()
    return execution


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seldrune Face GPU training worker")
    parser.add_argument(
        "--execution-manifest",
        type=Path,
        required=True,
        help="Path to an admitted Face GPU execution manifest",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    execution = load_execution_manifest(args.execution_manifest)
    print(
        json.dumps(
            {
                "status": "admitted",
                "job_id": execution.job_id,
                "model_version": execution.model_version,
                "accelerator": execution.accelerator,
                "execution_digest": execution.digest(),
                "max_steps": execution.max_steps,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
