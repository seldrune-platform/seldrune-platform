"""Executable entry point for admitted Seldrune Face GPU training jobs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from services.live_media.face_gpu_coordinator import coordinate_gpu_training
from services.live_media.face_gpu_execution import GpuTrainingExecution
from services.live_media.face_gpu_receipt_io import write_gpu_training_receipt
from services.live_media.face_gpu_training_bridge import execute_admitted_paired_training
from services.live_media.face_preprocessing import preprocess_training_bundle
from services.live_media.face_training_bundle import load_training_bundle


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


def run_training(
    execution: GpuTrainingExecution,
    model: Any,
    optimizer: Any,
    batches: Any,
) -> dict[str, Any]:
    result = execute_admitted_paired_training(
        execution,
        model,
        optimizer,
        batches,
        device="cuda",
    )
    return {
        "status": "trained",
        "job_id": execution.job_id,
        "execution_digest": execution.digest(),
        "completed_steps": result.completed_steps,
        "last_loss": result.last_loss,
        "device": result.device,
        "checkpoint_sha256": [item.sha256 for item in result.checkpoints],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seldrune Face GPU training worker")
    parser.add_argument("--execution-manifest", type=Path, required=True)
    parser.add_argument("--training-bundle", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--batch-size", type=int, default=16)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    execution = load_execution_manifest(args.execution_manifest)
    if args.training_bundle is None:
        print(json.dumps({
            "status": "admitted",
            "job_id": execution.job_id,
            "model_version": execution.model_version,
            "accelerator": execution.accelerator,
            "execution_digest": execution.digest(),
            "max_steps": execution.max_steps,
            "training_bridge": "blocked-cross-identity-target-required",
        }, sort_keys=True))
        return 0

    bundle = load_training_bundle(args.training_bundle)
    dataset = preprocess_training_bundle(bundle)
    coordinated = coordinate_gpu_training(
        execution,
        dataset.samples,
        batch_size=args.batch_size,
    )
    receipt_path = args.receipt or Path(execution.output_dir) / "gpu-training-receipt.json"
    write_gpu_training_receipt(coordinated.receipt, receipt_path)
    print(json.dumps({
        "status": "trained",
        "job_id": execution.job_id,
        "final_step": coordinated.receipt.final_step,
        "checkpoint_sha256": list(coordinated.receipt.checkpoint_sha256),
        "receipt": str(receipt_path),
        "last_loss": coordinated.last_loss,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
