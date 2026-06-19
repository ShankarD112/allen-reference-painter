"""Validate Allen Reference Painter saved ROI outputs.

Usage examples from the repo root:

    python scripts/validate_export.py outputs/ENT_painted_roi_YYYYMMDD_HHMMSS_metadata.json

or with explicit files:

    python scripts/validate_export.py metadata.json --faces face_ids.csv --mesh roi.ply
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from allen_reference_painter.export_validation import (  # noqa: E402
    summarize_results,
    validate_active_roi_export,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Allen Reference Painter ROI export files")
    parser.add_argument("metadata", help="Path to *_metadata.json from Save active ROI")
    parser.add_argument("--faces", help="Optional explicit painted face ID CSV")
    parser.add_argument("--mesh", help="Optional explicit exported ROI mesh, usually .ply")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results = validate_active_roi_export(args.metadata, face_csv=args.faces, mesh_path=args.mesh)
    print(summarize_results(results))
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
