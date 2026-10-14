# Browser Reference Painter

The browser workspace is a Vite/Three.js static application in this repository.
The existing Python desktop application remains available.

## Run

Node.js 22.12+ or 24, plus Python 3.12 for the one-time atlas preparation:

```sh
npm ci
npm run atlas:prepare
npm run dev
npm run test:web
npm run build
npx playwright install chromium
npm run test:browser
```

For Vercel, import this repository, select the browser feature branch for a
preview, keep the root directory at the repository root, use the Vite preset,
`npm run build`, and output directory `dist`. No backend, database, environment
variables, or API keys are required. The build prepares atlas assets with Python
in an isolated build-time virtual environment; visitors need only a browser.
The first build downloads the pinned public reference atlas. `vercel.json` records the build settings.

## Included workflow

- Search the full pinned atlas terminology by acronym, name, or structure ID.
- Load exact normalized meshes on demand; show/hide regions and set opacity.
- Paint or erase original mesh surface faces; mirror across ML 5,700 µm.
- Undo/redo up to 50 strokes and clear the active ROI.
- Linked original 25 µm coronal and sagittal annotation slices, depth sliders,
  exact slice indices, slice planes, crosshair, cell and painted-centroid overlays.
- Import CSV, TSV, delimited TXT, and XLSX cell tables with explicit source units.
  XLSX reads the first worksheet. Legacy XLS is not supported in this web version;
  save it as XLSX or CSV first. Coordinate aliases match the desktop application.
- Metadata and gene-expression colors share a range across 2D and 3D. Text
  metadata uses categorical colors. Missing values use gray.
  Literal text filtering and per-row visibility preserve all original rows.
- Download active ROI or complete scene as ZIP (PLY, face/centroid CSV, metadata,
  and imported cell metadata/visibility). Downloads keep AP/DV/ML micrometres.
- Save/reopen editable JSON projects, verifying mesh hashes and face ID bounds
  before replacing the current workspace. Download 3D and slice PNGs.

Save an editable project before closing. There is no automatic cloud save,
account, collaboration, or cross-device synchronization. A before-unload prompt
protects unsaved work where the browser supports it. File contents are processed
locally. Static atlas assets are fetched from the host.

## Gene expression and metadata coloring

Import cell metadata first, choosing the coordinate units. Include a unique
`cell_id` for every row, alongside `x,y,z` (or the supported coordinate aliases).
Use the metadata search and Apply metadata color to choose a categorical field
such as `MECvsLEC` or a numeric field.

Then upload an optional expression matrix: **genes in rows, cell IDs in column
headers, gene names in the first column**. CSV, TSV, TXT and the first worksheet
of XLSX are supported. A blank top-left header from R's row-name export is valid:

```r
write.csv(metadata_saved, "cells.csv", row.names = FALSE)
write.csv(counts_saved, "expression.csv", row.names = TRUE)
```

Search for a gene, select it and click Apply gene color. Only one source controls
cell color at a time; applying metadata replaces gene coloring and vice versa.
Search alone does not change the active coloring. Single color resets the view.

Matching uses case-sensitive `cell_id` values after trimming surrounding spaces,
never row/column order. The match summary lists missing IDs on both sides.
Duplicate IDs or gene names, malformed values, or zero matching IDs reject the
new expression file without changing the current workspace. Unmatched metadata
cells and blank/NA values are gray; **zero is a measured value**, not missing.
Decimal and negative values are retained as supplied, with no normalization or
log transform. The scale uses all matched metadata cells, including hidden ones;
expression-only columns do not affect it.

Expression imports support up to 5 million values, 100 MB for text files and
15 MB for XLSX. Subset larger matrices before export. Replacing cell metadata
clears the previous expression table. Combining workspaces with duplicate cell
IDs is rejected when expression is attached; use Resume for the same dataset.

Editable JSON and full scene ZIPs retain the matrix and selected color source.
Scene ZIPs also include `gene_expression.csv` and can contain cells alone.
ROI-only exports contain the selected region, without cell/expression tables.
Standalone HTML retains displayed cell colors and their legend; share the ZIP
or JSON as well when the recipient needs to select other genes or edit data.

## Scientific contract

Data is **allen_mouse_25um, BrainGlobe atlas version 3.1**, orientation ASR,
shape `[528,320,456]`, resolution `[25,25,25]` µm. Coordinates are
`[AP,DV,ML]` from the BrainGlobe atlas origin, not bregma.

The atlas builder uses the public `mesh_from_structure` API, which performs
normalization and unit conversion. Float64 vertex coordinates and original
triangle ordering are preserved. It does not read raw Draco coordinates as
micrometres, remesh, simplify, or reorder triangles. SHA-256 is computed over
little-endian Float64 vertices followed by Int64 face indices, matching the
existing Python exporter. Each browser mesh load checks this identity.

The renderer uses a separate millimetre transformation for navigation. All
brush queries, project IDs, and analysis exports use the original arrays.
Painting selects surface triangles; it is not a volumetric segmentation.
Atlas meshes themselves are surfaces provided by BrainGlobe, not exact voxel
boundaries. Face IDs are meaningful only with the recorded geometry hash.

The bundle has 855 mesh files. The pinned source has no mesh for `RSPd4`;
search marks this as unavailable. Annotation slices are actual annotation
voxel labels, not intersections of simplified Brain Party geometry.

## Data packaging

Generated atlas binaries are excluded from Git. `npm run build` prepares them
when absent; CI does the same before testing. A ready local bundle is reused.

```sh
python scripts/build_web_atlas.py --cache /path/to/cache
```

Use the Python dependencies in `pyproject.toml`. The script pins atlas version
3.1 and produces `public/data/atlas.json`, per-region compressed binary meshes,
and per-slice compressed Uint32 annotation labels. All source data is public
BrainGlobe/Allen reference data. No user cell data is bundled.

The complete static atlas bundle is approximately 316 MB. A visitor does not
load all of it: startup downloads the ~1 MB reference shell and terminology;
regions and slices load when requested. Large parent meshes can be tens of MB
and may need substantial browser memory. Desktop browsers are recommended.

## Verification

- Production build: passes in the development workspace.
- Six automated data tests: pass, including real ENT mesh identity, brush
  equivalence, coordinate conversion, and malformed project rejection.
- A real ENT ROI generated by the browser export routines passes the existing
  Python metadata, face table, and PLY validators.
- Browser integration coverage is in `web/e2e/workflow.spec.js` and runs in
  `.github/workflows/web.yml`. See the workflow results for browser verification;
  do not infer an interactive pass from a successful build alone.

Browser tests exercise real pointer painting, mirroring, undo/redo, cell
visibility, analysis ZIPs, editable project reopening, slices, import rejection,
and a narrow viewport. User acceptance on a physical GPU and representative
large cell datasets remains necessary before replacing the desktop release.


## Cell explorer controls (2026-10)

The paired Data uploads show each file's status. A persistent Showing badge names
all loaded datasets, including the synthetic example. Uploading metadata while
viewing the example stages the validated file: choose **Load your uploaded data**
to activate it, or keep the current data. Load pending metadata before its counts.

**Color by** searches genes and metadata in one grouped dropdown, with continuous
or categorical type labels. Continuous values support viridis, magma, plasma,
red-blue, grayscale, original, and custom two/three-stop scales. Min/max clipping
changes only displayed colors; source values and filters are unchanged. Empty
bounds use the data extent. The scale includes hidden cells for stability.

Shape uses categorical metadata; five symbols repeat for larger category sets,
with a notice. Size accepts numeric genes/metadata or discrete metadata categories;
missing sizes have their own legend entry. Both default to None. The same color,
shape and size encodings appear in 3D, slices and the optional embedding scatterplot.
The embedding uses uploaded numeric columns (preferring UMAP1/UMAP2); it does not
compute UMAP or t-SNE. Click a point or use Locate in the cell list to mark its
atlas coordinates and synchronize slices.

The collapsible summary reports category count, percent of all loaded cells and
visible count. Clicking a row isolates that category without changing manual
visibility. Category toggles and up to 50 gene ranges combine with AND. Each gene
has a histogram, draggable lower/upper sliders and exact numeric bounds. Missing
expression fails a gene filter. Histograms describe all measured metadata cells,
not just filtered cells. Clearing filters preserves manual Show/Hide choices.

Version-4 projects retain source identity, encodings, clipping, filters, summary
selection, embedding axes and manual visibility. Versions 1–3 remain readable.
Full scene ZIPs include these settings; ROI exports still exclude cells. Standalone
HTML keeps the displayed point geometry, colors, shapes, sizes and legends.

### One-file application code

`npm run build` also produces `dist/reference-painter.html`, containing all app
JavaScript, CSS, dependencies and the offline export runtime in one HTML file.
Serve this file over HTTP(S) beside the generated `data/` atlas directory. The
316 MB atlas remains external scientific data; it is not embedded in the code.
The normal modular source remains the maintainable source of truth. CI uploads
the single-file build with its browser verification artifacts.

Polish: paired upload cards, consistent form spacing and labels, compact channel
legends, collapsible analysis groups, a persistent source badge, accessible field
labels, and visible active/total cell counts.
