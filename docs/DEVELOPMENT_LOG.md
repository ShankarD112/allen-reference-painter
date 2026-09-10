# Desktop rebuild development log

## 2026-09-09 — Baseline and authorization

Request: remake the existing product into an intuitive, responsive desktop app; retain product development protocols; log the work; deliver a GitHub-downloadable Windows executable. Existing repository may be used. No merge or release has been performed.

Baseline: `984ca50` on `main`. Working branch: `feat/desktop-workflow-rebuild`.
Read the README, modular refactor plan, roadmap, coordinate-validation protocol and all relevant application/patch modules. No AGENTS.md, existing test suite, CONTRIBUTING guide, or CI workflows were present in the checked-out tree. Existing merge gate requires launch, regions, painting, cells/selection, 2D/3D updates, screenshots, and coordinate export validation.

## Audit findings

- Atlas loading/annotation materialization happens in the window constructor before the UI opens.
- Every paint sample scans all region face centroids with a full NumPy norm.
- Each paint sample builds a processed Trimesh and replaces its overlay actor.
- General scene refresh reconstructs imported cell geometry, labels, scalar styling and slice views.
- Slice updates clear Matplotlib figures, create axes and recompute layout each time.
- Markers and slice planes are removed and recreated on updates.
- The cell popup creates one table item for every cell/metadata value and repopulates on filter changes.
- Auto unit conversion tests voxel-size bounds before millimeter bounds, so typical millimeter values are classified as voxels. Units are fundamentally ambiguous from values alone.
- The console script launches the old prototype rather than the documented main entry point.
- Outputs are written relative to installed source, unsuitable for an executable installed in a protected directory.
- Export manifests use absolute paths and omit selected-cell state; moving a folder loses path references.
- Camera fixes are layered runtime wrappers which add additional render calls.

## Architecture decision

Keep Python, Qt/PySide6, VTK/PyVista, BrainGlobe and the original atlas-coordinate contracts. This preserves the specialized 3D/atlas functionality and follows the existing incremental migration protocol. Replace the workspace layout and performance-sensitive behavior in dedicated modules. Keep legacy launchers available for comparison. No web server, browser runtime, or cloud upload of scientific data is introduced.

The new coordinator reuses legacy scientific/metadata behavior by inheritance. This is an incremental rebuild, not a claim that all legacy code has been eliminated. Future removal of the legacy classes must follow the same feature gate.

## Implemented work

- New four-stage workspace, scalable splitter layout, quick guide, keyboard shortcuts, explicit Navigate/Paint/Erase tools, and offline synthetic demo.
- Atlas/reference initialization, region mesh loading, cell parsing/conversion and export file writing use worker threads; Qt and rendered VTK objects remain on the GUI thread.
- KD-tree brush queries preserve the original radius and nearest-face fallback, without remeshing atlas geometry.
- Persistent paint actor/mapper, markers and slice planes; paint update leaves cell geometry untouched.
- Slice update coalescing, persistent axes/images and a bounded 24-image annotation cache. Scatter overlays still update when required.
- Virtual cell table, literal filtering, selection preserving unit changes, matched numeric 2D/3D colors.
- Undo/redo (last 100 strokes), undoable clear, no painting while navigating, and active-mesh-only picking.
- Explicit unit confirmation instead of silently guessing. Malformed/nonfinite input rows fail visibly rather than being dropped. Out-of-bounds imports/conversions request an in-app decision.
- Portable atomic export directories with relative paths, ROI face IDs/centroids, atlas origin/units/axes, all imported cell coordinates and per-cell selection.
- User-writable outputs and rotating local logs (5 MB × current plus four backups). Logs cover sessions, jobs/timings, status, named controls and stroke counts. Imported row content and per-hover cell metadata are not logged. Logs are diagnostics, not a replayable scientific provenance database.
- One entry point for installed source and executable; Windows PyInstaller folder packaging plus OS-specific CI and frozen-binary smoke gate.

## Validation / limitations at implementation checkpoint

- Local core suite: 6 tests passed (brush equivalence including nearest fallback, explicit/anisotropic units, ambiguous auto, invalid coordinates, alias import).
- Synthetic 300,000-face / 100-query benchmark recorded in `BRUSH_BENCHMARK.json`; verifies identical selected face IDs. This measures brush lookup only, not complete paint latency or end-to-end FPS.
- All Python sources compile.
- Local Qt/PyVista/BrainGlobe/Trimesh packages are absent. A dependency install did not complete because network approval was cancelled by the execution environment; an offline install found no cached packages. GUI/export tests have not yet run locally.
- Added Linux/Windows tests and synthetic GUI smoke, plus Windows executable build and frozen smoke. Results must be recorded below after CI runs; adding workflow files alone is not evidence of a working executable.
- Real Allen download/cache/offline behavior, large real cell files, interactive graphics performance and a clean Windows machine remain manual release gates.
- Atlas download has indeterminate progress and cannot safely be interrupted in-process. The UI stays visible and asks users to wait before closing a running job. Offline demo is available from the welcome screen.
- Full native objects and export snapshots still use memory proportional to loaded data. Cell-table filter text is precomputed; no claim of unlimited-size datasets.
- No scene reload was present in the baseline; exports remain analysis outputs, not editable project saves. This is stated in the guide and on close.
- Executables are unsigned development artifacts until the release checklist is satisfied. No release is published automatically.

## CI iteration 1 — review branch published

- Direct `git push` failed because the shell had no GitHub credentials. Published the exact checked-out tree through the authorized GitHub connector and opened draft PR #2. Verified the local Git tree equals the uploaded tree (`3d33ec13a1927d9dd764752d838dc67b2b349029`).
- Initial commit on GitHub: `f61be88764f9f75ca5585bf40850e5264a1b71c7`.
- Run `34372381697`: Linux core and export tests passed (10); table import failed because `libEGL.so.1` was absent. Moved system library installation before unit tests, since Qt imports need EGL even without a window.
- Removed duplicate feature-branch push triggers; PR updates still run all gates, and main pushes retain validation.
- Reviewed historical packaging run `28120738167`: failure was a launcher path outside the checkout. New spec resolves from the spec directory and includes its launcher in version control.
- Compacted slice options into an expandable panel so the primary view has room on smaller displays. Visual inspection remains pending.

- Windows iteration 1 passed all 11 unit tests and brush equivalence. Source GUI smoke failed during window creation; OpenGL initialization warnings appeared, but the Python traceback was only in the local diagnostic artifact. Enabled stderr diagnostics for self-test runs so CI directly records failures. Artifact download could not be inspected locally (HTTP 403); no passing GUI result is claimed.

## CI iteration 2 — Linux desktop passes

Run `34372832860`, commit `10a525f1085a5438bf0449b79f50e2bed2e02a9f`:

- Linux passed all 11 tests and the full offline GUI exercise, including painting/erase/undo, camera and actor reuse, cell conversion/selection, slices, PNG output and export validation. Diagnostic artifact includes workspace and scene screenshots.
- Windows passed all 11 unit tests. The window constructor reached Ready; the process then exited during native OpenGL initialization before the smoke callback. This is a graphics failure, not evidence of a Python startup exception.
- Followed PyVista's own CI setup: added the upstream headless display action pinned to v3 commit `9c1c7435d9635423c90d2c37489588c81673274a`, enabling Mesa OpenGL on ephemeral Windows CI runners. This is test infrastructure only; no software driver is bundled into end-user installations.
- Added a required PASS report check so source GUI gates cannot pass merely by exiting early. Launcher diagnostics now consistently use the application logger namespace.

Sources inspected: `pyvista/pyvistaqt/.github/workflows/ci.yml`, `pyvista/setup-headless-display-action/README.md`, action definition and Windows installation script. Runtime graphics on clean end-user Windows hardware remains a separate release gate.

## CI iteration 3 — Windows desktop passes; frozen startup fails

Run `34373285814`, commit `ff445a9dc311e567174163f8f128056ff68b94e2`:

- Linux and Windows passed all 11 unit tests and completed their offline GUI smoke reports. The Mesa CI setup resolved the Windows source graphics failure.
- PyInstaller successfully built the Windows folder executable, but that executable exited 1 during its smoke test. It was not uploaded as a usable application. Added application-log output directly to the executable test step to expose the packaged startup failure.
- Added a real-atlas integration gate on Linux (`--self-test-real`) to check actual BrainGlobe download, annotation structure, ENT mesh loading, painting and coordinate export. This is additional integration evidence, not a substitute for human anatomical review or clean-Windows hardware testing.
- The local checkout was restored from the GitHub review branch after the workspace reset. Pending integration-test changes were reconstructed and will be committed before relying on them.

## CI iteration 4 — real data exposes an atlas API incompatibility

Run `34411069097`: synthetic desktop tests still pass. The real atlas downloads and opens its annotation volume, but ENT loading failed because current BrainGlobe atlas v3 returns a lazy Draco cache path from `meshfile_from_structure`, not a ready OBJ/PLY. Directly reading it would also bypass the required XYZ/nanometer → atlas-axis/micron conversion.

Changed reference and region loading to BrainGlobe's public `mesh_from_structure` API. It performs the lazy download, decoding and normalization. Convert its meshio triangle arrays to Trimesh with `process=False`, preserving face order and normalized coordinates. Added tests for this adapter and invalid mesh handling. The file path adapter remains only for the synthetic demo/older adapters.

Inspected the upstream `brainglobe_atlasapi/core.py` and `structure_class.py` implementations to verify the normalization contract. The failed real-data gate is retained; it was not skipped to make packaging green.

- Applied the same public mesh adapter to legacy launchers so regression comparison is not defeated by the atlas v3 storage change. Exports now also record the actual atlas version and a SHA-256 of the loaded full-mesh vertex/face arrays, tying face IDs to one precise geometry rather than only a stable atlas name.

- Extended the frozen/source smoke to parse synthetic CSV, TSV, TXT and XLSX files, including the runtime-selected Excel engine, rather than only injecting an already-parsed DataFrame. Legacy XLS is implemented with xlrd but still needs a representative-file release check.

- CI run 34411472341 passed all 13 tests on Linux and Windows, both synthetic desktop workflows, and the real Allen atlas workflow (ENT, 11,458 triangles). The frozen executable failed before atlas loading because the transitive Wasmtime DLL was absent. Added explicit Wasmtime binary/data collection; preserving the executable launch gate.

- CI run 34412215929: all 13 tests and both source GUI workflows pass, including the expanded cell file readers; real Allen source integration passes. Wasmtime now loads in the executable. The next frozen failure is NGFF 0.36.2 calling inspect.getsource(dask.array.core.to_zarr). Verified the exact upstream tag py-v0.36.2 and added a focused PyInstaller hook preserving that module source (pyz+py), following https://pyinstaller.org/en/stable/hooks.html#hook-global-variables. Added real Allen integration to the executable gate as well as the synthetic workflow, so download/decompression and coordinate paths are exercised in the distributed runtime.

- 2026-09-10: Resumed from run 34413004766. All source gates pass and the actual Windows executable now passes its complete synthetic GUI workflow, including spreadsheet imports. Its first real atlas download fails in fsspec/tqdm because a windowed executable has sys.stderr=None. Applied the documented PyInstaller windowed-stream fallback at launcher startup (only absent streams), preserving application file logging. See https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#sys-stdin-sys-stdout-and-sys-stderr-in-noconsole-windowed-applications-windows-only. The real-atlas executable gate remains required.
