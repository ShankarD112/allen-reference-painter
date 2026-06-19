"""Validation helpers for Allen Reference Painter export files.

These helpers are intentionally independent from the Qt UI.  They let us check
saved ROI/scene outputs after using the app, especially whether the exported
face tables and metadata still describe atlas-coordinate data correctly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import trimesh

REQUIRED_METADATA_KEYS = {
    "atlas",
    "atlas_resolution_um",
    "atlas_shape",
}

REQUIRED_FACE_COLUMNS = {
    "area",
    "face_id",
    "center_x_um",
    "center_y_um",
    "center_z_um",
}


@dataclass(frozen=True)
class ValidationResult:
    """Simple validation result for exported painter outputs."""

    ok: bool
    path: str
    messages: tuple[str, ...]

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        if not self.messages:
            return f"[{status}] {self.path}"
        return f"[{status}] {self.path}\n" + "\n".join(f"  - {m}" for m in self.messages)


def _as_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def load_json(path: str | Path) -> dict:
    """Load a JSON file as a dictionary."""

    with open(_as_path(path), "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def atlas_size_um(metadata: dict) -> np.ndarray:
    """Return atlas physical size in microns from export metadata."""

    shape = np.asarray(metadata["atlas_shape"], dtype=float)
    resolution = np.asarray(metadata["atlas_resolution_um"], dtype=float)
    if shape.shape != (3,) or resolution.shape != (3,):
        raise ValueError("atlas_shape and atlas_resolution_um must each have three values")
    return shape * resolution


def validate_metadata(metadata_path: str | Path) -> ValidationResult:
    """Validate a saved metadata JSON file."""

    path = _as_path(metadata_path)
    messages: list[str] = []
    try:
        metadata = load_json(path)
    except Exception as exc:  # noqa: BLE001 - collect validation failure text
        return ValidationResult(False, str(path), (f"Could not read JSON: {exc}",))

    missing = sorted(REQUIRED_METADATA_KEYS.difference(metadata))
    if missing:
        messages.append(f"Missing required metadata keys: {', '.join(missing)}")

    for key in ["atlas_shape", "atlas_resolution_um"]:
        if key in metadata:
            try:
                values = np.asarray(metadata[key], dtype=float)
                if values.shape != (3,):
                    messages.append(f"{key} should contain exactly 3 values")
                if np.any(values <= 0):
                    messages.append(f"{key} should contain positive values")
            except Exception as exc:  # noqa: BLE001
                messages.append(f"Could not parse {key}: {exc}")

    if "atlas_shape" in metadata and "atlas_resolution_um" in metadata:
        try:
            size_um = atlas_size_um(metadata)
            messages.append(
                "Atlas coordinate extent: "
                f"x={size_um[0]:.1f} um, y={size_um[1]:.1f} um, z={size_um[2]:.1f} um"
            )
        except Exception as exc:  # noqa: BLE001
            messages.append(f"Could not compute atlas size: {exc}")

    failures = [m for m in messages if m.startswith("Missing") or "should" in m or m.startswith("Could not")]
    return ValidationResult(not failures, str(path), tuple(messages))


def validate_face_table(face_csv: str | Path, metadata_path: str | Path | None = None) -> ValidationResult:
    """Validate a painted face ID CSV.

    When metadata is supplied, face centroids are also checked against the atlas
    physical extents implied by atlas_shape * atlas_resolution_um.
    """

    path = _as_path(face_csv)
    messages: list[str] = []
    try:
        df = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(False, str(path), (f"Could not read CSV: {exc}",))

    missing = sorted(REQUIRED_FACE_COLUMNS.difference(df.columns))
    if missing:
        messages.append(f"Missing required face-table columns: {', '.join(missing)}")
        return ValidationResult(False, str(path), tuple(messages))

    if df.empty:
        messages.append("Face table is empty")
        return ValidationResult(False, str(path), tuple(messages))

    if df["face_id"].duplicated().any():
        n_dup = int(df["face_id"].duplicated().sum())
        messages.append(f"Duplicate face_id entries detected: {n_dup}")

    coords = df[["center_x_um", "center_y_um", "center_z_um"]].apply(pd.to_numeric, errors="coerce").to_numpy()
    if not np.all(np.isfinite(coords)):
        messages.append("Some face centroid coordinates are not finite numbers")
    else:
        mins = coords.min(axis=0)
        maxs = coords.max(axis=0)
        messages.append(
            "Face centroid ranges: "
            f"x={mins[0]:.1f}..{maxs[0]:.1f} um, "
            f"y={mins[1]:.1f}..{maxs[1]:.1f} um, "
            f"z={mins[2]:.1f}..{maxs[2]:.1f} um"
        )

    if metadata_path is not None and np.all(np.isfinite(coords)):
        try:
            metadata = load_json(metadata_path)
            size_um = atlas_size_um(metadata)
            below = coords < 0
            above = coords > size_um[None, :]
            if np.any(below) or np.any(above):
                n_bad = int(np.any(below | above, axis=1).sum())
                messages.append(f"Coordinates outside atlas extent: {n_bad} rows")
        except Exception as exc:  # noqa: BLE001
            messages.append(f"Could not use metadata for coordinate bounds check: {exc}")

    failures = [
        m
        for m in messages
        if m.startswith("Missing")
        or m.startswith("Duplicate")
        or m.startswith("Some")
        or m.startswith("Coordinates outside")
        or m.startswith("Could not")
        or m.startswith("Face table is empty")
    ]
    return ValidationResult(not failures, str(path), tuple(messages))


def validate_mesh(mesh_path: str | Path) -> ValidationResult:
    """Validate that an exported mesh can be loaded and has geometry."""

    path = _as_path(mesh_path)
    messages: list[str] = []
    try:
        mesh = trimesh.load(path, force="mesh")
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(False, str(path), (f"Could not load mesh: {exc}",))

    if mesh.vertices.size == 0 or mesh.faces.size == 0:
        messages.append("Mesh has no vertices or faces")
    else:
        messages.append(f"Mesh vertices: {len(mesh.vertices)}")
        messages.append(f"Mesh faces: {len(mesh.faces)}")
        bounds = np.asarray(mesh.bounds, dtype=float)
        messages.append(
            "Mesh bounds: "
            f"x={bounds[0, 0]:.1f}..{bounds[1, 0]:.1f} um, "
            f"y={bounds[0, 1]:.1f}..{bounds[1, 1]:.1f} um, "
            f"z={bounds[0, 2]:.1f}..{bounds[1, 2]:.1f} um"
        )

    failures = [m for m in messages if m.startswith("Could not") or m.startswith("Mesh has no")]
    return ValidationResult(not failures, str(path), tuple(messages))


def validate_active_roi_export(
    metadata_path: str | Path,
    face_csv: str | Path | None = None,
    mesh_path: str | Path | None = None,
) -> list[ValidationResult]:
    """Validate the files produced by the current `Save active ROI` workflow."""

    metadata_path = _as_path(metadata_path)
    metadata = load_json(metadata_path)

    if face_csv is None:
        face_csv = metadata.get("face_ids_file")
    if mesh_path is None:
        mesh_path = metadata.get("ply_file")

    results = [validate_metadata(metadata_path)]
    if face_csv:
        results.append(validate_face_table(face_csv, metadata_path))
    else:
        results.append(ValidationResult(False, str(metadata_path), ("No face_ids_file provided",)))
    if mesh_path:
        results.append(validate_mesh(mesh_path))
    else:
        results.append(ValidationResult(False, str(metadata_path), ("No ply_file provided",)))
    return results


def summarize_results(results: Iterable[ValidationResult]) -> str:
    """Return a readable multi-file validation summary."""

    return "\n\n".join(result.summary() for result in results)
