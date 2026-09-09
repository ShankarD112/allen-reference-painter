# Release gate

Preserve the original `docs/MODULAR_REFACTOR.md` merge rule. Do not merge or publish a release until all required checks have evidence.

- [x] Linux and Windows unit suites pass (13 tests; run 34412215929).
- [ ] Source desktop smoke passes, with inspectable workspace/scene PNGs.
- [ ] Windows executable build succeeds and **the actual executable** passes its smoke test.
- [ ] Inspect the UI at 1080×760, typical 1440×980, and Windows 125%/150% scaling.
- [ ] On clean Windows, extract the downloaded artifact and double-click `AllenReferencePainter.exe` without Python installed.
- [ ] First real Allen atlas download succeeds with a responsive loading window; cached launch works offline.
- [ ] Search/load ENT, SUB, PERI, CA1; check visibility, active selection, region and paint colors, camera controls and transparency.
- [ ] Paint/erase at different angles, continuous strokes, mirror across the ML midline, undo/redo/clear; verify no rotation during painting.
- [ ] Import the example mm CSV and representative CSV/TSV/TXT/XLS/XLSX files; verify axis mapping, explicit units, invalid-row errors and out-of-bounds decisions.
- [ ] Compare selected cells, labels and numeric colors across 3D/coronal/sagittal views. Ensure selection remains unchanged after a units change.
- [ ] Verify all screenshot buttons, legends and filesystem failure dialogs.
- [ ] Export active ROI and full scene, move the export directory, run `scripts/validate_export.py` and compare face IDs/centroids to the loaded source mesh.
- [ ] Benchmark end-to-end paint/slice/cell-filter latency and memory on real target-size data. Brush-query microbenchmark alone is insufficient.
- [ ] Inspect logs for actionable failures and absence of imported cell row content.
- [ ] Record exact resolved dependencies, build SHA, artifact checksums, test evidence and outstanding limitations.

CI builds development artifacts for review. Publishing a tagged GitHub Release and code signing are separate release operations.

## Automated evidence

Run 34412215929 passes the Linux and Windows source desktop workflow, including synthetic file imports (CSV/TSV/TXT/XLSX), painting, selection, screenshots and export validation. Linux also passes the real Allen atlas workflow. Screenshot files are generated for review; no manual visual inspection or clean end-user Windows test has been recorded. The remaining boxes above intentionally require their stated evidence.
