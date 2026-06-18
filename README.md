# Allen Reference Painter

Python desktop app for viewing Allen Mouse atlas meshes, painting custom 3D ROIs, importing cell coordinates, and saving atlas-coordinate outputs for later Python analysis.

## Goals

- Load BrainGlobe `allen_mouse_25um` atlas meshes.
- Show a transparent reference brain model.
- Load Allen regions and subregions by acronym or name.
- Paint or erase ROI faces on the active mesh.
- Import cell x/y/z coordinate tables.
- Save ROI meshes, face IDs, cell coordinates, and scene metadata.

## Install

```bash
conda create -n allen-painter python=3.11
conda activate allen-painter
pip install -r requirements.txt
```

## Download/check atlas

```bash
python -c "from brainglobe_atlasapi.bg_atlas import BrainGlobeAtlas; BrainGlobeAtlas('allen_mouse_25um')"
```

## Run

```bash
python -m allen_reference_painter.app
```
