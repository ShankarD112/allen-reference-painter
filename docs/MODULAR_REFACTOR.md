# Modular refactor plan

Branch: `refactor/modular-app-structure`

This branch introduces the target module structure while keeping the current working modern app safe.

## Target structure

```text
src/allen_reference_painter/
├── __init__.py
├── main.py
├── app.py
├── theme.py
├── atlas.py
├── meshes.py
├── painting.py
├── cells.py
├── cell_table.py
├── views_2d.py
├── views_3d.py
├── screenshots.py
└── widgets.py
```

## First safe pass

The first pass adds standalone modules and keeps the current launcher working through:

```bash
python -m allen_reference_painter.main
```

This currently delegates to `app_modern.py` while logic is moved out incrementally.

## Migration order

1. Move constants and style into `theme.py`.
2. Move standalone cell-table popup into `cell_table.py`.
3. Move screenshot helpers into `screenshots.py`.
4. Move 2D styling/overlay helpers into `views_2d.py`.
5. Move 3D scene styling helpers into `views_3d.py`.
6. Move paint/mirror helper logic into `painting.py`.
7. Move cell coordinate utility logic into `cells.py`.
8. Move mesh state/loading/export helpers into `meshes.py`.
9. Keep `app.py`/`app_modern.py` as the coordinator until the new module boundary is stable.

## Merge rule

Do not merge this branch into `main` until:

- `python -m allen_reference_painter.main` launches successfully.
- region loading still works.
- cell import and selection still work.
- 2D and 3D views still update.
- screenshot buttons still save PNGs.
