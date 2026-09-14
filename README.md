# Allen Reference Painter

Explore the Allen mouse brain atlas, paint custom regions of interest on 3D meshes, compare cell coordinates in 3D and anatomical slices, and export atlas-space data for analysis.

## Desktop rebuild — development branch

This branch introduces a guided workspace and replaces expensive paint/render updates. It is under validation. **A ready-to-use Windows release is not yet published.** See [development log](docs/DEVELOPMENT_LOG.md) and [release gates](docs/RELEASE_CHECKLIST.md) for what has actually been tested.

### Windows download and launch

When the **Desktop validation and Windows build** workflow succeeds, download its `AllenReferencePainter-Windows-x64` artifact from the GitHub Actions run, extract the entire ZIP, and double-click `AllenReferencePainter.exe`. Keep the accompanying `_internal` folder next to it. Python, Conda and a terminal are not required for the packaged app. These development artifacts require GitHub sign-in; final release assets should be published only after the release gate passes.

The first real atlas load requires internet access and downloads BrainGlobe reference data. Subsequent loads reuse the local BrainGlobe cache. The welcome screen also offers an offline practice demo using **synthetic geometry, not Allen anatomy**. The app does not silently substitute demo anatomy for a failed atlas load.

### Four steps

1. **Regions:** search an acronym or full name, load its mesh, and select the active region. Show/hide regions and adjust transparency.
2. **Paint:** choose Paint or Erase, then click/drag on the active surface. Adjust brush radius, mirror across the midline, and undo with Ctrl+Z. Navigate rotates the scene without painting; Esc returns to Navigate.
3. **Cells:** choose source units and import a table. Choose labels and numeric colors, then filter the visible cells. Coronal/sagittal slices use the same numeric heatmap range as 3D.
4. **Export:** save active ROI or full scene, or capture 3D/slice screenshots. Use **Open output folder** to find screenshots, and choose a destination for analysis exports.

ROI painting selects mesh **surface faces**. It does not create a volumetric segmentation. Exports are analysis files; the app does not yet reload them as editable projects.

### Cell files and coordinate conventions

Supported: CSV, TSV, delimited TXT, XLS and XLSX. Coordinates accept aliases:

| Axis | Accepted columns |
|---|---|
| AP | `x`, `x_um`, `atlas_x`, `ap`, `ap_um` |
| DV | `y`, `y_um`, `atlas_y`, `dv`, `dv_um` |
| ML | `z`, `z_um`, `atlas_z`, `ml`, `ml_um` |

Coordinates use the **BrainGlobe atlas origin**, not bregma. Choose microns, millimeters (×1000), or voxel indices (×atlas resolution per axis). Auto detect asks you to confirm the source units because values alone are ambiguous. Missing/non-numeric coordinates are reported with data-row numbers; they are not silently discarded. Other columns are retained as metadata.

[Example cells](examples/example_cells.csv) use **millimeters**. Choose `Name` for labels and `Tau` or `Rn` for numeric colors. Cell-table filtering is literal text matching; Show/Hide filtered applies to matching rows and leaves other selections intact.

### Outputs and logs

Scene exports contain full region meshes, painted ROI meshes, face ID/centroid tables and JSON metadata. Cell exports preserve all imported rows, converted `app_x_um`, `app_y_um`, `app_z_um`, and an `app_selected` visibility column. File references are relative so export folders remain portable. Atlas resolution, shape, axis order, origin and units accompany the outputs.

Default screenshots and local logs live in:

- Windows: `%LOCALAPPDATA%\AllenReferencePainter\`
- macOS: `~/Library/Application Support/AllenReferencePainter/`
- Linux: `${XDG_DATA_HOME:-~/.local/share}/allen-reference-painter/`

Use the app's folder buttons rather than finding these paths manually. `ALLEN_PAINTER_DATA_DIR` overrides the location for tests/managed installations. Diagnostics rotate at 5 MB, with four backups. They include operations/timings/errors and stroke/control events; cell row values and hover content are excluded. No application telemetry is uploaded.

Validate a moved or original ROI export:

```bash
python scripts/validate_export.py /path/to/export/ENT_metadata.json
```

### Run from source

Python 3.11 is used by the build pipeline. From the repository root:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m allen_reference_painter.main
```

The `allen-reference-painter` command uses the same launcher. Legacy `app` and `app_modern` modules remain available for regression comparison, but are not the recommended launchers.

```bash
python -m allen_reference_painter.main --demo
python -m unittest discover -s tests -v
python -m allen_reference_painter.main --self-test --self-test-output smoke-output
python scripts/benchmark_brush.py
```

On headless Linux, run the smoke command under `xvfb-run -a` with the Qt/OpenGL system libraries installed. The smoke test uses synthetic data and does not establish correctness of real Allen anatomy.

### Build the Windows executable

Run on Windows in a clean Python 3.11 environment:

```powershell
python -m pip install -e '.[dev]'
python -m PyInstaller --noconfirm packaging/AllenReferencePainter.spec
.\dist\AllenReferencePainter\AllenReferencePainter.exe
```

The folder build avoids unpacking a large scientific runtime on every launch. Build on the target operating system: [PyInstaller is not a cross-compiler](https://www.pyinstaller.org/). CI tests source on Linux/Windows, builds on Windows, and tests the frozen executable before uploading it. The atlas is downloaded separately rather than bundled.

### Development protocol

Work on a feature branch, log decisions and verification, and preserve the coordinate-aware export contract. Follow [the existing modular refactor plan](docs/MODULAR_REFACTOR.md), [coordinate validation](docs/EXPORT_COORDINATE_VALIDATION.md) and [release checklist](docs/RELEASE_CHECKLIST.md). Do not merge a major UI/refactor until launch, region loading, painting, cell import/selection, 2D/3D updates and screenshots pass.

Implementation modules include `desktop.py` (coordination), `workspace_ui.py` (layout), `spatial.py` (brush index), `jobs.py` (background work), `cell_table.py` (virtual table), `exporting.py` (portable exports), and `runtime.py` (paths/logs). Legacy scientific behavior is reused while the migration proceeds.

## macOS and navigation update (0.3)

Mesh search now uses a visible results list with exact acronyms ranked first,
multiword matching, a result count, and no 250-result limit. Select a result and
choose Load region (or press Enter in the list). Up/Down in the search field
moves through results. Loading respects your selected row.

Both slice views have a slider and exact zero-based slice input. Position labels
show AP/ML microns from the atlas origin. Dashed lines show the other slice's
intersection, and matching yellow coronal / cyan sagittal planes are visible in
3D by default. Hide them in Slice display options when desired. Slider updates
are coalesced to avoid rendering on every input event.

The desktop workflow now builds separate macOS **Apple Silicon (arm64)** and
**Intel (x86_64)** apps on macOS 15 runners. Download the appropriate development
artifact after its tests pass, extract the inner ZIP, and move
`AllenReferencePainter.app` to Applications. Python is bundled. These development
builds are not Developer ID signed or notarized and are not yet trusted public
releases. Target macOS 15 or newer until older versions have been validated.

See [trusted distribution](docs/TRUSTED_DISTRIBUTION.md) for signing, notarization,
credentials, and release verification. No security-warning bypass is part of the
installation workflow.
