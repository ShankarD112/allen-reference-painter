# Roadmap

## Phase 1: Python app foundation

- Keep the app runnable as a Python desktop app.
- Load the Allen Mouse 25um atlas through BrainGlobe.
- Show a transparent reference brain shell before or behind loaded region meshes.
- Load arbitrary Allen regions/subregions by acronym or name.
- Keep current painting, erasing, symmetry, and color behavior.
- Use Allen structure colors when possible.
- Import cell coordinate tables and display x/y/z points in 3D and 2D views.
- Save painted ROI meshes, face IDs, face centroids, full colored meshes, cell coordinates, and metadata.

## Phase 2: Analysis outputs

- Add scripts/notebooks to compare painted ROIs with imported cells.
- Add point-in-mesh or nearest-mesh summaries.
- Add ROI overlap summaries by Allen structure.

## Phase 3: Packaging

- Add PyInstaller build scripts after the Python app is stable.
- Build Windows and macOS releases on their respective operating systems.
