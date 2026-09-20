"""Command-line verifier for Seldrune Face product-delivery evidence."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from services.live_media.face_production_io import load_production_gates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify Seldrune Face production evidence")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    return parser


def verify_production_files(
    evidence_path: str | Path,
    receipt_path: str | Path,
) -> dict[str, object]:
    gates = load_production_gates(evidence_path, receipt_path)
    values = asdict(gates)
    return {
        "status": "verified" if all(values.values()) else "partial",
        **values,
    }


def main() -> int:
    args = build_parser().parse_args()
    result = verify_production_files(args.evidence, args.receipt)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
