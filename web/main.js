import "./style.css";
import {readExpression} from './expression-import.js';
import {activeColoring,buildCellColoring,matchExpression,metadataIds} from './expression.js';
import { findRegions } from "./regions.js";
import { ensureLayers, newLayer, syncPaint, snapshot, restore, surfaceBrush, modifyMask } from './paint.js';
import { readProject, mergeProjects } from './session.js';
import { exportHTML } from './share.js';
import Papa from "papaparse";
import readXlsxFile from "read-excel-file/browser";
import { loadManifest, loadMesh } from "./atlas.js";
import { parseCells, mirrorPoint } from "./core.js";
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
  expression: null,
  coloring: {source:"single",key:""},
  mode: "navigate",
  dirty: false,
};
let filteredRegions = [], cancelLoad = false, bulkLoading = false;
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
    $("region-color").value = r.color;
    $("opacity").value = Math.round(r.opacity * 100);
    $("opacity-value").textContent = Math.round(r.opacity * 100) + "%";
  }
  renderLoaded();
  renderLayers();
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
      search(); dirty();
    };
    row.append(check, choose, remove);
    list.append(row);
  }
}
function search() {
  if (!state.manifest) return;
  const results = findRegions(state.manifest.regions, $("search").value, $("main-region").value);
  filteredRegions = results;
  $("search-results").replaceChildren();
  for (const r of results) {
    const button = document.createElement("button");
    button.className = "result";
    button.disabled = !r.file || busy || bulkLoading;
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
async function addRegion(info, bulk = false) {
  if (busy) return;
  if (state.regions.has(info.id)) {
    active(info.id);
    if (!bulk) viewer.focus(info.id);
    return;
  }
  busy = true;
  search();
  status(`Loading ${info.acronym}…`);
  try {
    const r = await loadMesh(info);
    ensureLayers(r, state.paintColor, state.mirrorColor);
    viewer.add(r);
    state.regions.set(r.id, r);
    active(r.id);
    if (!bulk) { slices.entries.forEach((e) => slices.focus(e)); viewer.focus(r.id); }
    dirty();
    status(
      `${r.acronym} loaded · ${r.triangles.toLocaleString()} original mesh faces`,
    );
  } finally {
    busy = false;
    search();
  }
}
function renderLayers() {
  const r = state.regions.get(state.active), list = $("paint-layers");
  list.replaceChildren();
  for (const id of ['layer-name', 'layer-tags', 'add-layer', 'delete-layer', 'isolate-layer', 'show-layers']) $(id).disabled = !r;
  if (!r) { $("layer-name").value = ''; $("layer-tags").value = ''; return; }
  const selected = ensureLayers(r, state.paintColor, state.mirrorColor);
  $("layer-name").value = selected.name; $("layer-tags").value = selected.tags;
  $("paint-color").value = selected.color; $("mirror-color").value = selected.mirrorColor;
  const filter = $("layer-filter").value.toLowerCase();
  for (const layer of r.layers) {
    if (!`${layer.name} ${layer.tags} ${layer.source || ''}`.toLowerCase().includes(filter)) continue;
    const row = document.createElement('div'); row.className = 'layer-row' + (layer.id === selected.id ? ' active' : '');
    const check = document.createElement('input'); check.type = 'checkbox'; check.checked = layer.visible;
    check.setAttribute('aria-label', 'Show layer ' + layer.name);
    check.onchange = () => { layer.visible = check.checked; refreshPaint(r); };
    const button = document.createElement('button');
    button.textContent = layer.name + (layer.tags ? ' · ' + layer.tags : '') + (layer.source ? ' — ' + layer.source : '');
    button.style.borderLeft = `5px solid ${layer.color}`;
    button.onclick = () => { r.activeLayer = layer.id; renderLayers(); dirty(); };
    row.append(check, button); list.append(row);
  }
}
function refreshPaint(r) { syncPaint(r); viewer.update(r); slices.refresh(); syncCounts(); dirty(); }
function begin() {
  const r = state.regions.get(state.active);
  if (r) { ensureLayers(r, state.paintColor, state.mirrorColor); stroke = { id: r.id, before: snapshot(r) }; }
}
function paint(hit) {
  const r = state.regions.get(state.active);
  if (!r || !r.visible) return;
  const layer = ensureLayers(r, state.paintColor, state.mirrorColor);
  if (!layer.visible) { status('Show the active paint layer before painting.'); return; }
  const radius = Number($("radius").value);
  const ids = $("brush-shape").value === 'surface' ? surfaceBrush(r, hit.face, hit.point, radius) : r.index.near(hit.point, radius);
  const painted = new Set(layer.painted), mirrored = new Set(layer.mirrored), erase = state.mode === 'erase';
  for (const id of ids) { erase ? painted.delete(id) : painted.add(id); mirrored.delete(id); }
  if ($("mirror").checked) {
    const p = mirrorPoint(hit.point, state.manifest.atlas_shape[2] * state.manifest.atlas_resolution_um[2] / 2);
    const original = new Set(ids);
    let reflected = r.index.near(p, radius);
    if ($("brush-shape").value === 'surface' && reflected.length) {
      const closest = reflected.reduce((best, id) => {
        const distance = f => [0,1,2].reduce((sum,a) => sum + (r.centroids[f * 3 + a] - p[a]) ** 2, 0);
        return distance(id) < distance(best) ? id : best;
      });
      reflected = surfaceBrush(r, closest, p, radius);
    }
    for (const id of reflected) {
      if (erase) { painted.delete(id); mirrored.delete(id); }
      else { painted.add(id); if (!original.has(id)) mirrored.add(id); }
    }
  }
  layer.painted = [...painted]; layer.mirrored = [...mirrored]; refreshPaint(r);
}
function end() {
  if (!stroke) return;
  const r = state.regions.get(stroke.id);
  if (r) {
    stroke.after = snapshot(r);
    if (JSON.stringify(stroke.before) !== JSON.stringify(stroke.after)) {
      undo.push(stroke); if (undo.length > 50) undo.shift(); redo = [];
    }
  }
  stroke = null; syncCounts();
}
function history(back) {
  const source = back ? undo : redo, target = back ? redo : undo, change = source.pop();
  if (!change) return;
  const r = state.regions.get(change.id);
  restore(r, change[back ? 'before' : 'after']); target.push(change);
  active(r.id); refreshPaint(r);
}
state.cellColor = () => "#16bda5";
function updateCells() {
  const colors = buildCellColoring(state.cells,state.expression,activeColoring(state));
  state.colorInfo = colors; state.cellColor = colors.color; state.range = colors.range;
  viewer.setCells(state.cells?.cells || [], state.cellColor);
  slices.refresh();
  $("active-coloring").textContent = colors.label;
  $("active-coloring").dataset.source = colors.source;
  $("color-legend").hidden = !colors.range;
  $("color-range").replaceChildren();
  if(colors.range)for(const x of colors.range){const span=document.createElement('span');span.textContent=String(x);$("color-range").append(span);}
  $("category-legend").replaceChildren();
  for(const entry of colors.categories){const row=document.createElement('div'),swatch=document.createElement('i'),label=document.createElement('span');swatch.style.background=entry.color;label.textContent=entry.label;row.append(swatch,label);$("category-legend").append(row);}
  $("color-missing").textContent=colors.source==='single'?'':`${colors.missing} cells with missing values (gray). ${colors.range?'Scale uses all matched cells, including hidden cells.':''}`;
  renderCellTable();
}
function applyColoring(source,key='') {
  if(source!=='single'&&!key){status('Select a field or gene first.',true);return;}
  const coloring={source,key};buildCellColoring(state.cells,state.expression,coloring);
  state.coloring=coloring;state.colorColumn=source==='metadata'?key:'';
  updateCells();dirty();status(`${state.colorInfo.label} applied to 3D and both slice views.`);
}
function metadataOptions() {
  const select=$('cell-color'),chosen=select.value||state.colorColumn,query=$('metadata-search').value.trim().toLowerCase();
  select.replaceChildren(new Option('Choose metadata field…',''));
  for(const h of state.cells?.headers||[])if(h.toLowerCase().includes(query))select.add(new Option(h,h));
  if([...select.options].some(o=>o.value===chosen))select.value=chosen;
  else if(query&&select.options.length>1)select.selectedIndex=1;
}
function geneOptions() {
  const select=$('gene-select'),chosen=select.value||(state.coloring.source==='gene'?state.coloring.key:''),query=$('gene-search').value.trim().toLowerCase();
  const genes=(state.expression?.genes||[]).filter(g=>g.toLowerCase().includes(query)).sort((a,b)=>Number(b.toLowerCase()===query)-Number(a.toLowerCase()===query)||a.localeCompare(b));
  const shown=genes.slice(0,100);if(chosen&&genes.includes(chosen)&&!shown.includes(chosen))shown.push(chosen);
  select.replaceChildren(new Option('Choose a gene…',''));for(const gene of shown)select.add(new Option(gene,gene));
  if(shown.includes(chosen))select.value=chosen;else if(query&&shown.length)select.selectedIndex=1;
  $('gene-count').textContent=state.expression?`${genes.length.toLocaleString()} matching genes${genes.length>100?' · first 100 shown; refine your search':''}`:'';
  $('apply-gene').disabled=!select.value||busy;
}
function expressionControls() {
  const data=state.expression;
  $('gene-search').disabled=!data;$('gene-select').disabled=!data;$('remove-expression').hidden=!data;
  $('expression-details').hidden=!data;
  if(data){const summary=matchExpression(data,state.cells);$('expression-summary').textContent=`${data.genes.length.toLocaleString()} genes · ${summary.matched} / ${summary.metadataTotal} metadata cells matched`;
    const summarize=values=>values.length?values.slice(0,20).join(', ')+(values.length>20?'…':''):'none';
    $('expression-unmatched').textContent=`Metadata IDs without expression (${summary.unmatchedMetadata.length}): ${summarize(summary.unmatchedMetadata)}. Expression IDs without coordinates (${summary.unmatchedExpression.length}): ${summarize(summary.unmatchedExpression)}. Matching is case-sensitive after trimming surrounding spaces.`;
  }else{$('expression-summary').textContent='No expression file loaded.';$('expression-unmatched').textContent='';}
  geneOptions();
}
async function importExpression(file) {
  if(busy)return;
  const table=state.cells;metadataIds(table);busy=true;document.querySelector('.workspace').inert=true;
  $('expression-summary').textContent='Reading expression matrix…';status('Matching gene expression to cell IDs…');
  try {const expression=await readExpression(file,table,()=>{$('expression-summary').textContent='Reading and validating gene rows…';});
    state.expression=expression;
    if(state.coloring.source==='gene'&&!expression.genes.includes(state.coloring.key))state.coloring={source:'single',key:''};
    $('gene-search').value='';updateCells();dirty();status('Expression loaded. Search a gene and apply its color.');
  } finally {busy=false;document.querySelector('.workspace').inert=false;expressionControls();}
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
    if(state.colorInfo?.source!=="single")label.title += `\n${state.colorInfo.label}: ${state.colorInfo.value(cell) ?? "missing"}`;
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
  const data=state.cells;$("cell-controls").hidden=!data;
  $("metadata-search").value='';$("gene-search").value='';$("cell-filter").value='';
  $('cell-label').replaceChildren(new Option('Row number',''));
  for(const h of data?.headers||[])$('cell-label').add(new Option(h,h));
  $('cell-label').value=state.labelColumn;
  metadataOptions();expressionControls();updateCells();
}
function acceptRows(rows, units) {
  const parsed = parseCells(rows, units, state.manifest.atlas_resolution_um);
  state.cells = parsed;
  state.expression = null;
  state.coloring = {source:"single",key:""};
  state.labelColumn = parsed.headers.find((h) => h.toLowerCase() === "cell_id") || parsed.headers.find((h) => /name|label/i.test(h)) || "";
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
function captureView() {
  state.view = { position: viewer.camera.position.toArray(), target: viewer.controls.target.toArray(),
    shell: $("shell").checked, planes: $("planes").checked, slices: slices.entries.map(e => e.index) };
}
function startWorkspace() {
  document.body.classList.remove('home');
  slices?.planes(); slices?.refresh(); viewer?.render();
}
async function openProjects(files, forceReplace = false) {
  if (!state.manifest || busy || bulkLoading) throw Error('Wait for atlas loading to finish.');
  const replace = forceReplace || $("import-mode").value === 'replace';
  if (replace && state.dirty && !confirm('Replace the current workspace with the saved files?')) return;
  busy = true; document.querySelector(".workspace").inert = true; search(); status('Validating saved files…');
  try {
    captureView();
    let data = replace ? null : projectData(state);
    for (const file of files) {
      const incoming = await readProject(file, state.manifest);
      data = data ? mergeProjects(data, incoming, file.name) : incoming;
    }
    if (!data) return;
    validateProject(data, state.manifest);
    const prepared = [];
    for (const saved of data.regions) {
      const source = state.manifest.regions.find(r => r.id === saved.id), r = await loadMesh(source);
      Object.assign(r, { painted: new Set(saved.painted), mirrored: new Set(saved.mirrored), visible: saved.visible,
        opacity: saved.opacity, color: saved.color || source.color, layers: saved.layers, activeLayer: saved.activeLayer });
      ensureLayers(r, data.paintColor, data.mirrorColor); syncPaint(r); prepared.push(r);
    }
    // Commit only after every file and mesh has validated successfully.
    for (const id of state.regions.keys()) viewer.remove(id);
    state.regions.clear(); state.paintColor = data.paintColor; state.mirrorColor = data.mirrorColor;
    for (const r of prepared) { state.regions.set(r.id, r); viewer.add(r); }
    state.cells = data.cells ?? null; state.labelColumn = data.labelColumn || ''; state.colorColumn = data.colorColumn || ''; state.expression = data.expression || null; state.coloring = activeColoring(data);
    undo = []; redo = []; active(data.active); setupCells(); startWorkspace();
    if (data.view) {
      viewer.camera.position.fromArray(data.view.position); viewer.controls.target.fromArray(data.view.target); viewer.controls.update();
      $("shell").checked = data.view.shell; viewer.shell.visible = data.view.shell;
      $("planes").checked = data.view.planes;
      slices.entries.forEach((e, i) => { e.index = data.view.slices[i]; slices.load(e); });
      slices.planes(); viewer.render();
    } else if (data.active) { viewer.focus(data.active); slices.entries.forEach(e => slices.focus(e)); }
    state.dirty = !replace; status('Project restored. Labels, meshes, painted faces and cell data are ready.');
  } finally { busy = false; document.querySelector(".workspace").inert = false; search(); }
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
$("region-color").oninput = () => {
  const r = state.regions.get(state.active); if (!r) return;
  r.color = $("region-color").value; viewer.update(r); dirty();
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
    const r = state.regions.get(state.active);
    if (r) {
      const layer = ensureLayers(r, state.paintColor, state.mirrorColor);
      layer[key === 'paintColor' ? 'color' : 'mirrorColor'] = state[key]; viewer.update(r); renderLayers();
    }
    slices.refresh();
    dirty();
  };
$("undo").onclick = () => history(true);
$("redo").onclick = () => history(false);
$("clear-roi").onclick = () => {
  const r = state.regions.get(state.active);
  if (!r?.painted.size) return;
  begin();
  const layer = ensureLayers(r, state.paintColor, state.mirrorColor);
  layer.painted = []; layer.mirrored = []; syncPaint(r);
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
    Array.from({ length: 96 }, (_, i) => ({
      Name: `Cell ${String(i + 1).padStart(2, '0')}`, Dataset: 'Synthetic demonstration',
      Group: i % 2 ? 'Right' : 'Left', AP: +(7.8 + (i % 12) * 0.13).toFixed(2),
      DV: +(3.6 + (Math.floor(i / 12) % 4) * 0.4).toFixed(2),
      ML: +(i % 2 ? 9.5 - (i % 7) * 0.12 : 1.9 + (i % 7) * 0.12).toFixed(2), Tau: +(12 + (i * 7 % 37) * 0.7).toFixed(1)
    })),
    "mm",
  );
};
$("cell-label").onchange = () => {
  state.labelColumn = $("cell-label").value;
  updateCells();
  dirty();
};
$("cell-color").onchange = () => {if($('cell-color').value)applyColoring('metadata',$('cell-color').value);};
$('apply-metadata').onclick=()=>applyColoring('metadata',$('cell-color').value);
$('metadata-search').oninput=metadataOptions;
$('gene-search').oninput=geneOptions;
$('gene-select').onchange=()=>{$('apply-gene').disabled=!$('gene-select').value;};
$('apply-gene').onclick=()=>applyColoring('gene',$('gene-select').value);
$('clear-cell-color').onclick=()=>applyColoring('single');
$('expression-file').onchange=async()=>{const file=$('expression-file').files[0];if(!file)return;try{await importExpression(file);}catch(error){fail(error);}finally{$('expression-file').value='';}};
$('remove-expression').onclick=()=>{state.expression=null;if(state.coloring.source==='gene')state.coloring={source:'single',key:''};expressionControls();updateCells();dirty();};
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
      captureView();
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
  captureView();
  download(
    JSON.stringify(projectData(state)),
    `allen_painter_project_${Date.now()}.json`,
    "application/json",
  );
  state.dirty = false;
  status("Editable project downloaded.");
};
$("project-file").onchange = async () => {
  const files = [...$("project-file").files];
  if (!files.length) return;
  try {
    await openProjects(files);
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
    const mainAcronyms = new Set(['Isocortex', 'OLF', 'HPF', 'CTXsp', 'STR', 'PAL', 'TH', 'HY', 'MB', 'P', 'MY', 'CB', 'fiber tracts', 'VS']);
    for (const r of state.manifest.regions.filter(r => mainAcronyms.has(r.acronym)).sort((a,b) => a.name.localeCompare(b.name))) {
      const option = document.createElement('option'); option.value = r.id; option.textContent = r.name; $("main-region").append(option);
    }
    $("search").value = "";
    search();
    active(null);
    viewer.planes.forEach(p => p.visible = false);
    viewer.render();
    $("start").disabled = false; $("home-upload").disabled = false;
    $("loading").hidden = true;
    status(
      "Atlas ready. Start painting or upload saved work.",
    );
  } catch (err) {
    $("loading-message").textContent = err.message;
    $("retry").hidden = false;
    fail(err);
  } finally {
    initRunning = false;
  }
}
$("start").disabled = true; $("home-upload").disabled = true;
$("start").onclick = startWorkspace;
$("home-upload").onclick = () => { $("import-mode").value = 'replace'; $("project-file").click(); };
$("main-region").onchange = search;
$("layer-filter").oninput = renderLayers;
for (const [id, key] of [['layer-name', 'name'], ['layer-tags', 'tags']]) $(id).onchange = () => {
  const r = state.regions.get(state.active); if (!r) return;
  begin(); ensureLayers(r, state.paintColor, state.mirrorColor)[key] = $(id).value.trim() || (key === 'name' ? 'Untitled ROI' : ''); end(); renderLayers(); dirty();
};
$("add-layer").onclick = () => {
  const r = state.regions.get(state.active); if (!r) return; begin();
  const layer = newLayer('ROI ' + (r.layers.length + 1), state.paintColor, state.mirrorColor);
  r.layers.push(layer); r.activeLayer = layer.id; end(); renderLayers(); dirty();
};
$("delete-layer").onclick = () => {
  const r = state.regions.get(state.active); if (!r) return; begin();
  r.layers = r.layers.filter(l => l.id !== r.activeLayer);
  if (!r.layers.length) r.layers.push(newLayer()); r.activeLayer = r.layers[0].id;
  refreshPaint(r); end(); renderLayers();
};
for (const id of ['isolate-layer', 'show-layers']) $(id).onclick = () => {
  const r = state.regions.get(state.active); if (!r) return;
  r.layers.forEach(l => l.visible = id === 'show-layers' || l.id === r.activeLayer); refreshPaint(r); renderLayers();
};
for (const button of document.querySelectorAll('[data-mask]')) button.onclick = () => {
  const r = state.regions.get(state.active); if (!r) return status('Load a region first.');
  begin(); modifyMask(r, ensureLayers(r, state.paintColor, state.mirrorColor), button.dataset.mask); end(); refreshPaint(r);
};
$("load-all").onclick = async () => {
  if (busy || bulkLoading) return;
  const selected = filteredRegions.filter(r => r.file && !state.regions.has(r.id));
  if (selected.length > 50 && !confirm(`Load ${selected.length} meshes? This can use substantial memory. Choose a main region to load a smaller set.`)) return;
  bulkLoading = true; cancelLoad = false; $("cancel-load").hidden = false;
  $("load-all").disabled = true; $("remove-all").disabled = true;
  try {
    for (const r of selected) {
      if (cancelLoad) break;
      await addRegion(r, true);
      await new Promise(resolve => requestAnimationFrame(resolve));
    }
    viewer.view('3d'); status(cancelLoad ? 'Mesh loading stopped. Loaded meshes are retained.' : 'Matching meshes loaded.');
  } catch (e) { fail(e); } finally {
    bulkLoading = false; $("cancel-load").hidden = true; $("load-all").disabled = false; $("remove-all").disabled = false; search();
  }
};
$("cancel-load").onclick = () => { cancelLoad = true; };
$("remove-all").onclick = () => {
  if (busy || bulkLoading) return;
  if ([...state.regions.values()].some(r => r.painted.size) && !confirm('Remove all meshes and their paint layers? Save your work first if you want to keep it.')) return;
  for (const id of state.regions.keys()) viewer.remove(id);
  state.regions.clear(); undo = []; redo = []; active(null); search(); dirty();
};
$("export-html").onclick = async () => {
  if (busy || bulkLoading) return;
  busy = true; status('Preparing standalone interactive HTML…');
  try { await exportHTML(viewer, state.colorInfo); status('Interactive HTML downloaded. Open it offline or share the file.'); }
  catch (e) { fail(e); } finally { busy = false; }
};
$("retry").onclick = init;
init();
