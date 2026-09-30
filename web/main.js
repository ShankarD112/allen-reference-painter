import "./style.css";
import Papa from "papaparse";
import readXlsxFile from "read-excel-file/browser";
import { loadManifest, loadMesh } from "./atlas.js";
import { parseCells, mirrorPoint, numericRange, heatColor } from "./core.js";
import { Viewer } from "./viewer.js";
import { Slices } from "./slices.js";
import {
  download,
  exportAnalysis,
  projectData,
  validateProject,
} from "./export.js";
const $ = (id) => document.getElementById(id);
const state = {
  manifest: null,
  regions: new Map(),
  active: null,
  cells: null,
  paintColor: "#ff795f",
  mirrorColor: "#55d9e7",
  labelColumn: "",
  colorColumn: "",
  mode: "navigate",
  dirty: false,
};
let viewer,
  slices,
  undo = [],
  redo = [],
  stroke = null,
  busy = false,
  initRunning = false;
const status = (message, error = false) => {
  $("status").textContent = message;
  $("status").classList.toggle("error", error);
};
const fail = (err) => status(err.message || String(err), true);
function dirty() {
  state.dirty = true;
}
function tab(name) {
  document
    .querySelectorAll("[data-tab]")
    .forEach((b) => b.setAttribute("aria-selected", b.dataset.tab === name));
  document
    .querySelectorAll(".panel")
    .forEach((p) => (p.hidden = p.id !== "panel-" + name));
}
function setMode(mode) {
  state.mode = mode;
  viewer?.setMode(mode);
  document
    .querySelectorAll("[data-mode]")
    .forEach((b) => b.setAttribute("aria-pressed", b.dataset.mode === mode));
  $("mode-badge").textContent = mode.toUpperCase();
  if (mode !== "navigate" && !state.active)
    status("Load and select a region before painting.");
}
function syncCounts() {
  const r = state.regions.get(state.active);
  $("face-count").textContent = (r?.painted.size || 0).toLocaleString();
  $("undo").disabled = !undo.length;
  $("redo").disabled = !redo.length;
}
function active(id) {
  state.active = id;
  viewer.active = id;
  const r = state.regions.get(id);
  $("active-title").textContent = r ? r.acronym : "Reference atlas";
  $("active-subtitle").textContent = r
    ? r.name
    : "Allen mouse · 25 µm · BrainGlobe 3.1";
  if (r) {
    $("opacity").value = Math.round(r.opacity * 100);
    $("opacity-value").textContent = Math.round(r.opacity * 100) + "%";
  }
  renderLoaded();
  syncCounts();
  slices?.refresh();
}
function renderLoaded() {
  const list = $("loaded-regions");
  list.replaceChildren();
  $("region-count").textContent = state.regions.size;
  if (!state.regions.size) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "Choose a region above to load its surface.";
    list.append(p);
    return;
  }
  for (const r of state.regions.values()) {
    const row = document.createElement("div");
    row.className = "region-row" + (state.active === r.id ? " active" : "");
    const check = document.createElement("input");
    check.type = "checkbox";
    check.checked = r.visible;
    check.setAttribute("aria-label", "Show " + r.acronym);
    check.onchange = () => {
      r.visible = check.checked;
      viewer.update(r);
      slices.refresh();
      dirty();
    };
    const choose = document.createElement("button");
    choose.textContent = r.acronym;
    choose.title = r.name;
    choose.onclick = () => active(r.id);
    const remove = document.createElement("button");
    remove.textContent = "×";
    remove.className = "remove";
    remove.setAttribute("aria-label", "Remove " + r.acronym);
    remove.onclick = () => {
      if (
        r.painted.size &&
        !confirm(`Remove ${r.acronym} and its painted ROI?`)
      )
        return;
      viewer.remove(r.id);
      state.regions.delete(r.id);
      undo = undo.filter((x) => x.id !== r.id);
      redo = redo.filter((x) => x.id !== r.id);
      active(
        state.active === r.id
          ? (state.regions.keys().next().value ?? null)
          : state.active,
      );
      dirty();
    };
    row.append(check, choose, remove);
    list.append(row);
  }
}
function search() {
  if (!state.manifest) return;
  const query = $("search").value.trim().toLowerCase(),
    terms = query.split(/\s+/).filter(Boolean);
  const results = state.manifest.regions
    .filter(
      (r) =>
        r.acronym !== "root" &&
        terms.every((t) =>
          `${r.acronym} ${r.name} ${r.id}`.toLowerCase().includes(t),
        ),
    )
    .sort(
      (a, b) =>
        Number(b.acronym.toLowerCase() === query) -
          Number(a.acronym.toLowerCase() === query) ||
        Number(b.acronym.toLowerCase().startsWith(query)) -
          Number(a.acronym.toLowerCase().startsWith(query)) ||
        a.acronym.localeCompare(b.acronym),
    );
  $("search-count").textContent = `${results.length} matching regions`;
  $("search-results").replaceChildren();
  for (const r of results) {
    const button = document.createElement("button");
    button.className = "result";
    button.disabled = !r.file || busy;
    button.setAttribute("aria-label", `Load ${r.acronym} — ${r.name}`);
    const swatch = document.createElement("span");
    swatch.className = "swatch";
    swatch.style.background = r.color;
    const text = document.createElement("span"),
      name = document.createElement("strong"),
      desc = document.createElement("small"),
      plus = document.createElement("span");
    name.textContent = r.acronym;
    desc.textContent = r.name + (r.file ? "" : " · mesh unavailable");
    text.append(name, desc);
    plus.className = "plus";
    plus.textContent = state.regions.has(r.id) ? "✓" : "+";
    button.append(swatch, text, plus);
    button.onclick = () => addRegion(r).catch(fail);
    $("search-results").append(button);
  }
}
async function addRegion(info) {
  if (busy) return;
  if (state.regions.has(info.id)) {
    active(info.id);
    viewer.focus(info.id);
    return;
  }
  busy = true;
  search();
  status(`Loading ${info.acronym}…`);
  try {
    const r = await loadMesh(info);
    viewer.add(r);
    state.regions.set(r.id, r);
    active(r.id);
    slices.entries.forEach((e) => slices.focus(e));
    viewer.focus(r.id);
    dirty();
    status(
      `${r.acronym} loaded · ${r.triangles.toLocaleString()} original mesh faces`,
    );
  } finally {
    busy = false;
    search();
  }
}
function begin() {
  const r = state.regions.get(state.active);
  if (r)
    stroke = {
      id: r.id,
      before: [...r.painted],
      beforeMirror: [...r.mirrored],
    };
}
function paint(hit) {
  const r = state.regions.get(state.active);
  if (!r || !r.visible) return;
  const radius = Number($("radius").value),
    ids = r.index.near(hit.point, radius);
  const erase = state.mode === "erase";
  for (const id of ids) {
    if (erase) {
      r.painted.delete(id);
      r.mirrored.delete(id);
    } else {
      r.painted.add(id);
      r.mirrored.delete(id);
    }
  }
  if ($("mirror").checked) {
    const p = mirrorPoint(
      hit.point,
      (state.manifest.atlas_shape[2] * state.manifest.atlas_resolution_um[2]) /
        2,
    );
    for (const id of r.index.near(p, radius)) {
      if (erase) {
        r.painted.delete(id);
        r.mirrored.delete(id);
      } else {
        r.painted.add(id);
        if (!ids.includes(id)) r.mirrored.add(id);
      }
    }
  }
  viewer.update(r);
  syncCounts();
  slices.refresh();
  dirty();
}
function end() {
  if (!stroke) return;
  const r = state.regions.get(stroke.id);
  if (r) {
    stroke.after = [...r.painted];
    stroke.afterMirror = [...r.mirrored];
    if (
      stroke.before.join(",") !== stroke.after.join(",") ||
      stroke.beforeMirror.join(",") !== stroke.afterMirror.join(",")
    ) {
      undo.push(stroke);
      if (undo.length > 50) undo.shift();
      redo = [];
    }
  }
  stroke = null;
  syncCounts();
}
function history(back) {
  const source = back ? undo : redo,
    target = back ? redo : undo,
    change = source.pop();
  if (!change) return;
  const r = state.regions.get(change.id);
  r.painted = new Set(change[back ? "before" : "after"]);
  r.mirrored = new Set(change[back ? "beforeMirror" : "afterMirror"]);
  target.push(change);
  active(r.id);
  viewer.update(r);
  slices.refresh();
  syncCounts();
  dirty();
}
state.cellColor = (cell) =>
  state.colorColumn
    ? heatColor(cell.row[state.colorColumn], state.range)
    : "#16bda5";
function updateCells() {
  if (!state.cells) return;
  state.range = state.colorColumn
    ? numericRange(state.cells.cells, state.colorColumn)
    : null;
  viewer.setCells(state.cells.cells, state.cellColor);
  slices.refresh();
  $("color-legend").hidden = !state.range;
  $("color-range").replaceChildren();
  if (state.range)
    for (const x of state.range) {
      const span = document.createElement("span");
      span.textContent = String(x);
      $("color-range").append(span);
    }
  renderCellTable();
}
function matches(cell) {
  const query = $("cell-filter").value.toLowerCase();
  return Object.values(cell.row).some((v) =>
    String(v ?? "")
      .toLowerCase()
      .includes(query),
  );
}
function renderCellTable() {
  const all = state.cells?.cells || [],
    selected = all.filter((c) => c.visible),
    filtered = all.filter(matches);
  $("cell-summary").textContent =
    `${selected.length} of ${all.length} cells visible · ${filtered.length} match filter`;
  $("cell-table").replaceChildren();
  for (const [i, cell] of all.entries()) {
    if (!matches(cell)) continue;
    if ($("cell-table").childElementCount >= 150) break;
    const row = document.createElement("div");
    row.className = "cell-item";
    const check = document.createElement("input");
    check.type = "checkbox";
    check.checked = cell.visible;
    check.id = "cell-" + i;
    check.onchange = () => {
      cell.visible = check.checked;
      dirty();
      updateCells();
    };
    const label = document.createElement("label");
    label.htmlFor = check.id;
    label.textContent = state.labelColumn
      ? String(cell.row[state.labelColumn] ?? `Row ${i + 1}`)
      : `Row ${i + 1}`;
    label.title = state.cells.headers
      .map((h) => `${h}: ${cell.row[h] ?? ""}`)
      .join("\n");
    const focus = document.createElement("button");
    focus.textContent = "Locate";
    focus.setAttribute("aria-label", "Locate " + label.textContent);
    focus.onclick = () => {
      viewer.setMarker(cell.xyz);
      slices.marker = cell.xyz;
      for (const e of slices.entries) {
        e.index = Math.max(
          0,
          Math.min(
            state.manifest.atlas_shape[e.axis] - 1,
            Math.round(cell.xyz[e.axis] / 25),
          ),
        );
        slices.load(e);
      }
      status(
        `Cell ${i + 1} · AP ${cell.xyz[0]} · DV ${cell.xyz[1]} · ML ${cell.xyz[2]} µm`,
      );
    };
    row.append(check, label, focus);
    $("cell-table").append(row);
  }
  if (filtered.length > 150) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = `Showing first 150 of ${filtered.length} matches. Refine the filter to see more.`;
    $("cell-table").append(p);
  }
}
function setupCells() {
  const data = state.cells;
  $("cell-controls").hidden = !data;
  if (!data) {
    viewer.setCells([], state.cellColor);
    return;
  }
  for (const id of ["cell-label", "cell-color"]) {
    const select = $(id);
    select.replaceChildren();
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = id === "cell-label" ? "Row number" : "Single color";
    select.append(empty);
    for (const h of data.headers) {
      if (id === "cell-color" && !numericRange(data.cells, h)) continue;
      const option = document.createElement("option");
      option.value = h;
      option.textContent = h;
      select.append(option);
    }
  }
  $("cell-label").value = state.labelColumn;
  $("cell-color").value = state.colorColumn;
  updateCells();
}
function acceptRows(rows, units) {
  const parsed = parseCells(rows, units, state.manifest.atlas_resolution_um);
  state.cells = parsed;
  state.labelColumn = parsed.headers.find((h) => /name|label/i.test(h)) || "";
  state.colorColumn = "";
  setupCells();
  dirty();
  const outside = parsed.cells.filter((c) =>
    c.xyz.some((v, a) => v < 0 || v >= state.manifest.atlas_shape[a] * 25),
  ).length;
  status(
    `${parsed.cells.length} cells imported${outside ? ` · ${outside} outside atlas bounds (retained)` : ""}`,
  );
}
async function importCells(file) {
  if (!state.manifest) throw Error("Wait for the atlas to load.");
  const units = $("units").value;
  if (!units) throw Error("Choose source coordinate units before importing.");
  if (file.size > 30 * 1024 * 1024)
    throw Error("Please use a cell table smaller than 30 MB.");
  let rows;
  if (file.name.toLowerCase().endsWith(".xlsx")) {
    const table = await readXlsxFile(file);
    if (table.length < 2) throw Error("The workbook has no data rows.");
    const headers = table[0].map((v) => String(v ?? "").trim());
    if (headers.some((h) => !h) || new Set(headers).size !== headers.length)
      throw Error("Spreadsheet headers must be nonempty and unique.");
    rows = table
      .slice(1)
      .filter((r) => r.some((v) => v !== null))
      .map((r) => Object.fromEntries(headers.map((h, i) => [h, r[i]])));
  } else {
    const parsed = Papa.parse(await file.text(), {
      header: true,
      skipEmptyLines: "greedy",
      delimiter: /\.tsv$/i.test(file.name) ? "\t" : "",
      transformHeader: (h) => h.trim(),
    });
    if (parsed.errors.length)
      throw Error("Could not parse table: " + parsed.errors[0].message);
    if (
      parsed.meta.renamedHeaders &&
      Object.keys(parsed.meta.renamedHeaders).length
    )
      throw Error("Table headers must be unique.");
    rows = parsed.data;
  }
  acceptRows(rows, units);
}
async function openProject(file) {
  if (!state.manifest || busy) throw Error("Wait for atlas loading to finish.");
  if (file.size > 50 * 1024 * 1024)
    throw Error("Project exceeds the 50 MB import limit.");
  const data = validateProject(JSON.parse(await file.text()), state.manifest);
  if (
    state.dirty &&
    !confirm("Replace the current workspace with this saved project?")
  )
    return;
  busy = true;
  status("Opening project…");
  try {
    const prepared = [];
    for (const saved of data.regions) {
      const source = state.manifest.regions.find((r) => r.id === saved.id),
        r = await loadMesh(source);
      Object.assign(r, {
        painted: new Set(saved.painted),
        mirrored: new Set(saved.mirrored),
        visible: saved.visible,
        opacity: saved.opacity,
      });
      prepared.push(r);
    }
    for (const id of state.regions.keys()) viewer.remove(id);
    state.regions.clear();
    state.paintColor = data.paintColor;
    state.mirrorColor = data.mirrorColor;
    viewer.paintColor = data.paintColor;
    viewer.mirrorColor = data.mirrorColor;
    $("paint-color").value = data.paintColor;
    $("mirror-color").value = data.mirrorColor;
    for (const r of prepared) {
      state.regions.set(r.id, r);
      viewer.add(r);
    }
    state.cells = data.cells ?? null;
    state.labelColumn = data.labelColumn || "";
    state.colorColumn = data.colorColumn || "";
    undo = [];
    redo = [];
    active(data.active);
    setupCells();
    if (data.active) {
      viewer.focus(data.active);
      slices.entries.forEach((e) => slices.focus(e));
    }
    state.dirty = false;
    status("Project restored. Mesh identities and face IDs verified.");
  } finally {
    busy = false;
    search();
  }
}
for (const b of document.querySelectorAll("[data-tab]"))
  b.onclick = () => tab(b.dataset.tab);
for (const b of document.querySelectorAll("[data-mode]"))
  b.onclick = () => setMode(b.dataset.mode);
for (const b of document.querySelectorAll("[data-view]"))
  b.onclick = () => viewer?.view(b.dataset.view);
$("search").oninput = search;
$("focus").onclick = () => viewer?.focus(state.active);
$("radius").oninput = () => {
  $("radius-value").textContent = $("radius").value + " µm";
};
$("opacity").oninput = () => {
  const r = state.regions.get(state.active);
  $("opacity-value").textContent = $("opacity").value + "%";
  if (r) {
    r.opacity = Number($("opacity").value) / 100;
    viewer.update(r);
    dirty();
  }
};
$("shell").onchange = () => {
  if (viewer?.shell) {
    viewer.shell.visible = $("shell").checked;
    viewer.render();
  }
};
for (const [id, key] of [
  ["paint-color", "paintColor"],
  ["mirror-color", "mirrorColor"],
])
  $(id).oninput = () => {
    state[key] = $(id).value;
    viewer[key] = state[key];
    for (const r of state.regions.values()) viewer.update(r);
    slices.refresh();
    dirty();
  };
$("undo").onclick = () => history(true);
$("redo").onclick = () => history(false);
$("clear-roi").onclick = () => {
  const r = state.regions.get(state.active);
  if (!r?.painted.size) return;
  begin();
  r.painted.clear();
  r.mirrored.clear();
  end();
  viewer.update(r);
  slices.refresh();
  dirty();
};
$("cell-file").onchange = async () => {
  const file = $("cell-file").files[0];
  if (!file) return;
  try {
    await importCells(file);
  } catch (e) {
    fail(e);
  } finally {
    $("cell-file").value = "";
  }
};
$("example-cells").onclick = () => {
  if (!state.manifest) return;
  $("units").value = "mm";
  acceptRows(
    [
      { Name: "Cell 01", AP: 8.8, DV: 4.5, ML: 2.0, Tau: 18.2 },
      { Name: "Cell 02", AP: 9.1, DV: 4.8, ML: 2.2, Tau: 26.5 },
      { Name: "Cell 03", AP: 8.9, DV: 4.3, ML: 9.3, Tau: 34.1 },
    ],
    "mm",
  );
};
$("cell-label").onchange = () => {
  state.labelColumn = $("cell-label").value;
  updateCells();
  dirty();
};
$("cell-color").onchange = () => {
  state.colorColumn = $("cell-color").value;
  updateCells();
  dirty();
};
$("cell-filter").oninput = renderCellTable;
for (const [id, visible] of [
  ["show-filtered", true],
  ["hide-filtered", false],
])
  $(id).onclick = () => {
    for (const c of state.cells?.cells || [])
      if (matches(c)) c.visible = visible;
    updateCells();
    dirty();
  };
for (const [id, activeOnly] of [
  ["export-roi", true],
  ["export-scene", false],
])
  $(id).onclick = async () => {
    if (busy) return;
    try {
      busy = true;
      status("Preparing analysis export…");
      await exportAnalysis(state, activeOnly);
      status(
        "Analysis ZIP downloaded. Coordinates remain in atlas micrometres.",
      );
    } catch (e) {
      fail(e);
    } finally {
      busy = false;
    }
  };
$("save-project").onclick = () => {
  if (!state.manifest) return;
  download(
    JSON.stringify(projectData(state)),
    `allen_painter_project_${Date.now()}.json`,
    "application/json",
  );
  state.dirty = false;
  status("Editable project downloaded.");
};
$("project-file").onchange = async () => {
  const file = $("project-file").files[0];
  if (!file) return;
  try {
    await openProject(file);
  } catch (e) {
    fail(e);
  } finally {
    $("project-file").value = "";
  }
};
$("screenshot").onclick = () => {
  if (viewer) download(viewer.screenshot(), "allen_painter_3d.png");
};
$("slice-screenshot").onclick = () => {
  if (slices) download(slices.screenshot(), "allen_painter_slices.png");
};
$("help").onclick = () => $("help-dialog").showModal();
$("close-help").onclick = () => $("help-dialog").close();
window.addEventListener("beforeunload", (e) => {
  if (state.dirty) {
    e.preventDefault();
    e.returnValue = "";
  }
});
window.addEventListener("keydown", (e) => {
  if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName)) return;
  if (e.key === "Escape") setMode("navigate");
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
    e.preventDefault();
    history(!e.shiftKey);
  }
});
async function init() {
  if (initRunning) return;
  initRunning = true;
  $("loading").hidden = false;
  $("retry").hidden = true;
  $("loading-message").textContent = "Preparing the atlas…";
  try {
    if (!viewer)
      viewer = new Viewer($("viewer"), {
        begin,
        paint,
        end,
        hover: (hit) => {
          $("hover-info").textContent =
            `AP ${hit.point[0].toFixed(0)} · DV ${hit.point[1].toFixed(0)} · ML ${hit.point[2].toFixed(0)} µm`;
        },
      });
    state.manifest = await loadManifest();
    if (!viewer.shell) {
      const root = state.manifest.regions.find((r) => r.acronym === "root");
      const mesh = await loadMesh(root);
      viewer.add(mesh, true);
    }
    if (!slices) slices = new Slices(state.manifest, state, viewer, status);
    $("search").value = "ENT";
    search();
    active(null);
    viewer.render();
    $("loading").hidden = true;
    status(
      `${state.manifest.regions.filter((r) => r.file).length} atlas meshes available. Search a region to begin.`,
    );
  } catch (err) {
    $("loading-message").textContent = err.message;
    $("retry").hidden = false;
    fail(err);
  } finally {
    initRunning = false;
  }
}
$("retry").onclick = init;
init();
