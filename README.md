# Allen Reference Painter

Python desktop app for viewing Allen Mouse atlas meshes, painting custom 3D ROIs, importing cell coordinates, visualizing cells in 3D/2D atlas space, and saving atlas-coordinate outputs for later Python analysis.

The current recommended launcher is:

```bash
python -m allen_reference_painter.main
```

`main.py` currently launches the modern UI and applies the small screenshot patch used during the modular refactor. The older direct launchers are still available, but `main.py` should be treated as the normal entry point going forward.

---

## Current features

- Load the BrainGlobe `allen_mouse_25um` atlas.
- Show a transparent reference brain shell at startup.
- Dynamically load Allen regions by acronym or name.
- Paint and erase ROI faces on the active mesh.
- Optional mirrored/symmetric painting across the atlas midline.
- Import cell coordinate tables from CSV/TSV/TXT/XLS/XLSX.
- Convert cell coordinates from microns, millimeters, voxel indices, or auto-detected units.
- Display imported cells in 3D.
- Label cells using metadata columns such as `Name`.
- Color cells by numeric metadata columns such as `Tau` or `Rn`.
- View selected cells in coronal and sagittal 2D slice panels.
- Use matching heatmap colors in 3D and 2D views.
- Select/deselect imported cells from a popup cell table.
- Save ROI meshes, painted face IDs, cell coordinates, scene metadata, and screenshots.

---

## Install

From the repo root:

```bash
conda create -n allen-painter python=3.11
conda activate allen-painter
pip install -r requirements.txt
pip install -e .
```

The `pip install -e .` step is important because this repo uses a `src/` package layout. Without it, Python may not find the `allen_reference_painter` package when running with `python -m`.

---

## Download/check the atlas

The first launch may download the BrainGlobe Allen atlas. You can also pre-check it with:

```bash
python -c "from brainglobe_atlasapi.bg_atlas import BrainGlobeAtlas; BrainGlobeAtlas('allen_mouse_25um')"
```

---

## Run

Recommended:

```bash
conda activate allen-painter
python -m allen_reference_painter.main
```

Older direct launchers are still available:

```bash
python -m allen_reference_painter.app_modern
python -m allen_reference_painter.app
```

Use `app_modern` only if you want the modern UI without the modular launcher patch. Use `app` only if you want the older stable prototype UI.

---

## Basic workflow

1. Launch the app.
2. Search for an Allen region by acronym or name, for example `ENT`, `SUB`, `PERI`, or `CA1`.
3. Load the region.
4. Set the active region.
5. Paint or erase ROI faces on the 3D mesh.
6. Optionally enable symmetry to mirror painting across the midline.
7. Load a cell coordinate table.
8. Choose the correct cell coordinate unit.
9. Choose a cell label column and numeric color column.
10. Use the 2D coronal/sagittal viewers to inspect painted ROIs and cells across atlas slices.
11. Save scene outputs and screenshots.

---

## Cell coordinate input

Cell files can be CSV, TSV, TXT, XLS, or XLSX.

Expected coordinate columns can use common names such as:

```text
x, x_um, atlas_x, ap, ap_um
y, y_um, atlas_y, dv, dv_um
z, z_um, atlas_z, ml, ml_um
```

Example table:

```text
Name,Tau,Rn,x,y,z
Aug012024IR3a,100,179.26,9.2532,5.7411,1.4887
Aug012024IR3b,8.25,40.94,9.5875,5.6056,1.8879
```

For coordinates like the example above, choose:

```text
Cell units = Millimeters (mm -> um x1000)
```

Then useful settings are usually:

```text
Cell label/hover = Name
Color cells by = Tau or Rn
2D cells use heatmap colors = on
```

---

## Cell table and selection

After loading cells, click:

```text
View cell table
```

The popup table lets you:

- Search/filter cell rows by text.
- Select or deselect individual cells.
- Select all or deselect all filtered rows.
- Apply the selection to both the 3D scene and 2D slice views.

Screenshots and visualizations use the currently visible/selected cells.

---

## 2D slice viewer

The right-side 2D viewer includes coronal and sagittal slice panels.

Useful controls:

```text
Cells on coronal
Cells on sagittal
2D cells use heatmap colors
```

The 2D cell colors match the selected numeric `Color cells by` column when heatmap coloring is enabled. The cell heatmap legend is shown at the bottom of the 2D side panel.

---

## Screenshots

The app provides screenshot buttons for:

```text
3D scene
Coronal
Sagittal
Both 2D
All views
```

Screenshots are saved into:

```text
outputs/
```

The 2D screenshot buttons save the 2D plot with the heatmap legend stacked underneath when heatmap coloring is active.

Example output names:

```text
3D_scene_YYYYMMDD_HHMMSS.png
coronal_2D_with_legend_YYYYMMDD_HHMMSS.png
sagittal_2D_with_legend_YYYYMMDD_HHMMSS.png
```

---

## Scene/ROI outputs

Scene and ROI export files are saved under timestamped output folders in:

```text
outputs/
```

Typical saved outputs include:

- Painted ROI mesh files.
- Painted face ID tables.
- Cell coordinate tables.
- Scene metadata JSON.
- Screenshot PNGs.

Exact file names depend on the loaded regions and save action.

---

## Project structure

The repo now has the beginning of a modular structure:

```text
src/allen_reference_painter/
├── __init__.py
├── main.py                  # recommended launcher entry point
├── app.py                   # original stable prototype app
├── app_modern.py            # current modern UI implementation
├── theme.py                 # shared colors and stylesheet constants
├── atlas.py                 # atlas config and region color helpers
├── meshes.py                # mesh state/helpers, to be expanded
├── painting.py              # painting/mirroring helpers, to be expanded
├── cells.py                 # cell coordinate utilities
├── views_2d.py              # 2D view helpers, to be expanded
├── views_3d.py              # 3D view helpers
├── screenshots.py           # screenshot path/save helpers
├── screenshot_legend_patch.py
└── widgets.py               # small Qt helper functions
```

The refactor is intentionally incremental. `app_modern.py` still coordinates most behavior, while newer modules are being introduced gradually so the working app does not break.

See also:

```text
docs/MODULAR_REFACTOR.md
```

---

## Development notes

Recommended development workflow:

```bash
git checkout main
git pull
conda activate allen-painter
python -m allen_reference_painter.main
```

For larger changes, create a new feature/refactor branch first, test locally, then merge back into `main` after the app launches and the core workflow still works.

Before merging major UI/refactor changes, test:

- App launches from `python -m allen_reference_painter.main`.
- Region search/loading works.
- Painting and erasing work.
- Cell import works.
- Cell selection table works.
- 2D heatmap coloring works.
- Screenshot buttons save expected PNGs.
