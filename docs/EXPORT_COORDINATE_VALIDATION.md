# Export and Coordinate Validation

This branch focuses on making sure the existing save/export behavior is reliable before changing the UI.

The current app already has two important save paths:

- **Save active ROI**: saves the currently painted faces for the active region.
- **Save scene/meshes**: saves all loaded full region meshes, painted ROI meshes, painted face ID tables, imported cell coordinates, and a scene manifest.

The main scientific requirement is that saved outputs remain tied to the Allen / BrainGlobe reference coordinate system, rather than only being visual screenshots or colors.

---

## What should be true for a saved ROI

A saved painted ROI should preserve:

1. The exported mesh geometry.
2. The face IDs that were painted on the original region mesh.
3. The face centroid coordinates in atlas microns.
4. Atlas metadata, including atlas name, shape, and resolution.
5. Enough metadata to reload and interpret the output later in Python.

For rough custom-border teaching models, this is enough to use the app as a visual annotation tool and then clean/smooth/refine the borders later in Python.

---

## Current active ROI output files

When using **Save active ROI**, the app currently creates files like:

```text
outputs/ENT_painted_roi_YYYYMMDD_HHMMSS.ply
outputs/ENT_painted_roi_YYYYMMDD_HHMMSS_face_ids.csv
outputs/ENT_painted_roi_YYYYMMDD_HHMMSS_metadata.json
```

The face ID CSV should contain:

```text
area,face_id,center_x_um,center_y_um,center_z_um
```

Those centroid columns are the key coordinate-aware output. They should be in the same atlas micron coordinate space as the loaded BrainGlobe/Allen meshes.

---

## Validate an exported active ROI

From the repo root:

```bash
python scripts/validate_export.py outputs/ENT_painted_roi_YYYYMMDD_HHMMSS_metadata.json
```

The validator reads the metadata JSON and follows the recorded paths to the saved face table and mesh.

You can also pass explicit files:

```bash
python scripts/validate_export.py \
  outputs/ENT_painted_roi_YYYYMMDD_HHMMSS_metadata.json \
  --faces outputs/ENT_painted_roi_YYYYMMDD_HHMMSS_face_ids.csv \
  --mesh outputs/ENT_painted_roi_YYYYMMDD_HHMMSS.ply
```

A good result should show `PASS` for:

- metadata JSON
- painted face table
- ROI mesh

It also prints useful coordinate ranges, for example:

```text
Face centroid ranges: x=..., y=..., z=... um
Mesh bounds: x=..., y=..., z=... um
```

---

## Manual testing checklist

Use this checklist when testing the branch locally.

### 1. Launch

```bash
python -m allen_reference_painter.main
```

Expected:

- App opens.
- Reference brain appears.
- Region search is available.

### 2. Load region

Try a region like:

```text
ENT
```

Expected:

- Region loads in the 3D viewer.
- Region appears in the loaded region table.
- Active region can be selected.

### 3. Paint rough ROI

Paint a small patch on the active region.

Expected:

- Painted overlay appears.
- Status bar reports painted face count.
- 2D slice overlays show painted face centroids if ROI-on-slices is enabled.

### 4. Save active ROI

Click:

```text
Save active ROI
```

Expected:

- `.ply`, `_face_ids.csv`, and `_metadata.json` are saved in `outputs/`.
- The face CSV has one row per painted face.
- The coordinate columns are populated in microns.

### 5. Validate active ROI

Run:

```bash
python scripts/validate_export.py outputs/<your_metadata_file>.json
```

Expected:

- Metadata validation passes.
- Face table validation passes.
- Mesh validation passes.
- Face centroid ranges and mesh bounds look reasonable for Allen atlas micron coordinates.

### 6. Save full scene

Click:

```text
Save scene/meshes
```

Expected:

- A timestamped `outputs/scene_YYYYMMDD_HHMMSS/` folder is created.
- Full region mesh files are saved.
- Painted ROI mesh/table files are saved for painted regions.
- `scene_manifest.json` records all exported files.

---

## What this branch does not solve yet

This branch does **not** yet add perfect custom-border editing or automatic smoothing. That is intentional.

The current goal is to make the rough teaching/annotation workflow trustworthy:

```text
Load Allen mesh -> paint rough custom domains -> save coordinate-aware output -> refine later in Python
```

---

## Possible next improvements

After this validation passes locally, the next useful improvements would be:

1. Save one CSV with both face IDs and all three vertex coordinates per face.
2. Save a color/label name for each painted ROI, not only the current paint color.
3. Save full-scene validation for `scene_manifest.json`.
4. Add a reload function for a saved painted ROI.
5. Add optional PLY vertex/face colors so the mesh itself carries visible paint colors when opened elsewhere.
