import {nearestCell,showCellHover,hideCellHover} from './cell-hover.js';
import {
  defaults,
  variables,
  token,
  fromToken,
  SCALES,
  SHAPES,
  category,
  summary,
  histogram,
  drawSymbol,
} from "./cell-explorer.js";
import { buildCellColoring } from "./expression.js";
const $ = (id) => document.getElementById(id);
const el = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};
export class CellControls {
  constructor(state, change, locate) {
    this.state = state;
    this.change = change;
    this.locate = locate;
    $("color-search").oninput = () =>
      this.options("color-by", $("color-search").value);
    $("color-by").onchange = () => this.applyColor();
    $("apply-color").onclick = () => this.applyColor();
    $("size-search").oninput = () =>
      this.options("size-by", $("size-search").value);
    $("size-by").onchange = () => {
      state.explorer.size = fromToken($("size-by").value);
      change();
    };
    $("shape-by").onchange = () => {
      state.explorer.shape = $("shape-by").value;
      change();
    };
    for (const name of Object.keys(SCALES))
      $("palette").add(new Option(name === "legacy" ? "Original" : name, name));
    $("palette").add(new Option("Custom (2–3 colors)", "custom"));
    $("palette").onchange = () => {
      state.explorer.palette = $("palette").value;
      change();
    };
    $("custom-count").onchange = () => {
      state.explorer.customCount = Number($("custom-count").value);
      change();
    };
    for (let i = 0; i < 3; i++)
      $("custom-" + i).oninput = () => {
        state.explorer.custom[i] = $("custom-" + i).value;
        change();
      };
    for (const id of ["clip-min", "clip-max"])
      $(id).onchange = () => this.clip();
    $("reset-clip").onclick = () => {
      state.explorer.min = null;
      state.explorer.max = null;
      change();
    };
    $("summary-by").onchange = () => {
      state.explorer.summary = $("summary-by").value;
      state.explorer.isolate = null;
      change();
    };
    $("clear-isolate").onclick = () => {
      state.explorer.isolate = null;
      change();
    };
    $("add-category").onclick = () => this.addCategory();
    $("filter-gene-search").oninput = () => this.geneOptions();
    $("add-gene-filter").onclick = () => this.addGene();
    $("clear-filters").onclick = () => {
      Object.assign(state.explorer, {
        categories: [],
        genes: [],
        isolate: null,
      });
      this.filters();
      change();
    };
    for (const [id, key] of [
      ["embedding-x", "embeddingX"],
      ["embedding-y", "embeddingY"],
    ])
      $(id).onchange = () => {
        state.explorer[key] = $(id).value;
        change();
      };
    $("embedding").onpointermove=event=>{const rect=$("embedding").getBoundingClientRect();const points=(this.points||[]).map(p=>({cell:p.cell,x:p.x*rect.width/600,y:p.y*rect.height/360,radius:3.5*this.state.cellChannels.size(p.cell)*rect.width/600}));showCellHover(nearestCell(points,event.clientX-rect.left,event.clientY-rect.top),event);};
    $("embedding").onpointerleave=hideCellHover;
    $("embedding").onclick = (event) => {
      const box = $("embedding").getBoundingClientRect(),
        x = ((event.clientX - box.left) * 600) / box.width,
        y = ((event.clientY - box.top) * 360) / box.height;
      let best = null,
        distance = 144;
      for (const p of this.points || []) {
        const d = (p.x - x) ** 2 + (p.y - y) ** 2;
        if (d < distance) {
          distance = d;
          best = p.cell;
        }
      }
      if (best) this.locate(best);
    };
  }
  applyColor() {
    const choice = fromToken($("color-by").value) || {
      source: "single",
      key: "",
    };
    this.state.coloring = choice;
    this.state.colorColumn = choice.source === "metadata" ? choice.key : "";
    this.state.explorer.min = null;
    this.state.explorer.max = null;
    this.change();
  }
  options(id, query = "") {
    const select = $(id),
      chosen =
        select.value ||
        (id === "color-by"
          ? token(
              this.state.coloring?.source === "single"
                ? null
                : this.state.coloring,
            )
          : token(this.state.explorer.size));
    const matches = this.vars.filter((v) =>
      v.key.toLowerCase().includes(query.trim().toLowerCase()),
    );
    select.replaceChildren(
      new Option(id === "color-by" ? "Single color" : "None", ""),
    );
    for (const [source, label] of [
      ["gene", "Genes"],
      ["metadata", "Metadata"],
    ]) {
      const group = el("optgroup");
      group.label = label;
      const all = matches.filter((v) => v.source === source),
        shown = all.slice(0, 150);
      const current = all.find((v) => token(v) === chosen);
      if (current && !shown.includes(current)) shown.push(current);
      for (const v of shown)
        group.append(new Option(`${v.key} · ${v.type}`, token(v)));
      if (shown.length) select.append(group);
    }
    if (chosen && [...select.options].some((o) => o.value === chosen))
      select.value = chosen;
    else if (query && select.options.length > 1) select.selectedIndex = 1;
    if (id === "color-by")
      $("variable-count").textContent =
        `${matches.length.toLocaleString()} matching variables${matches.length > 150 ? " · refine search to see more" : ""}`;
  }
  refresh() {
    this.state.explorer ??= defaults();
    this.vars = variables(this.state);
    for (const id of ["color-search", "size-search", "filter-gene-search"])
      $(id).value = "";
    $("color-by").replaceChildren();
    $("size-by").replaceChildren();
    this.options("color-by");
    this.options("size-by");
    const metadata = this.vars.filter((v) => v.source === "metadata"),
      categorical = metadata.filter((v) => v.type === "categorical"),
      numeric = metadata.filter((v) => v.type === "continuous");
    for (const [id, list, first] of [
      ["shape-by", categorical, "None"],
      ["summary-by", metadata, "Choose metadata"],
      ["category-by", metadata, "Choose metadata"],
      ["embedding-x", numeric, "Choose X"],
      ["embedding-y", numeric, "Choose Y"],
    ]) {
      $(id).replaceChildren(new Option(first, ""));
      for (const v of list) $(id).add(new Option(v.key, v.key));
    }
    const s = this.state.explorer;
    if (!s.embeddingX)
      s.embeddingX =
        numeric.find((v) => /^(umap[_ .-]?1|tsne[_ .-]?1|pc1)$/i.test(v.key))
          ?.key ||
        numeric[0]?.key ||
        "";
    if (!s.embeddingY)
      s.embeddingY =
        numeric.find((v) => /^(umap[_ .-]?2|tsne[_ .-]?2|pc2)$/i.test(v.key))
          ?.key ||
        numeric[2]?.key ||
        numeric[1]?.key ||
        "";
    for (const [id, key] of [
      ["shape-by", "shape"],
      ["summary-by", "summary"],
      ["embedding-x", "embeddingX"],
      ["embedding-y", "embeddingY"],
    ])
      $(id).value = s[key];
    this.geneOptions();
    this.filters();
  }
  geneOptions() {
    const query = $("filter-gene-search").value.toLowerCase();
    $("filter-gene").replaceChildren(new Option("Choose gene", ""));
    for (const gene of (this.state.expression?.genes || [])
      .filter((g) => g.toLowerCase().includes(query))
      .slice(0, 150))
      $("filter-gene").add(new Option(gene, gene));
    if (query && $("filter-gene").options.length > 1)
      $("filter-gene").selectedIndex = 1;
  }
  clip() {
    const min = $("clip-min").value === "" ? null : Number($("clip-min").value),
      max = $("clip-max").value === "" ? null : Number($("clip-max").value);
    const extent = this.state.colorInfo.dataRange || this.state.colorInfo.range;
    if (
      [min, max].some((v) => v !== null && !Number.isFinite(v)) ||
      (extent && (min ?? extent[0]) > (max ?? extent[1]))
    ) {
      $("clip-error").textContent =
        "Minimum must be less than or equal to maximum.";
      return;
    }
    $("clip-error").textContent = "";
    Object.assign(this.state.explorer, { min, max });
    this.change();
  }
  render() {
    const state = this.state,
      info = state.colorInfo,
      s = state.explorer || defaults();
    $("dataset-badge").textContent = state.cells
      ? `Showing: ${state.dataSource?.name || "Restored cells"} · ${state.cells.cells.length.toLocaleString()} cells`
      : "Showing: no cell data";
    $("metadata-status").textContent = state.cells
      ? `${state.dataSource?.name || "Restored cells"} · loaded`
      : "No metadata loaded";
    $("palette-settings").hidden = !info.range;
    $("palette").value = s.palette;
    $("custom-colors").hidden = s.palette !== "custom";
    $("custom-count").value = s.customCount;
    s.custom.forEach((value, i) => {
      $("custom-" + i).value = value;
      $("custom-" + i).hidden = i >= s.customCount;
    });
    for (const [id, key, i] of [
      ["clip-min", "min", 0],
      ["clip-max", "max", 1],
    ]) {
      $(id).value = s[key] ?? "";
      $(id).placeholder = String(
        info.dataRange?.[i] ?? info.range?.[i] ?? "Auto",
      );
    }
    if (info.stops)
      $("color-legend").querySelector(".gradient").style.background =
        `linear-gradient(90deg,${info.stops.join(",")})`;
    this.legend(
      "shape-legend",
      state.cellChannels?.shapeLegend || [],
      "shape",
      s.shape ? "Shape · " + s.shape : "Shape · none",
    );
    this.legend(
      "size-legend",
      state.cellChannels?.sizeLegend || [],
      "size",
      s.size ? "Size · " + s.size.key : "Size · none",
    );
    this.table();
    this.embedding();
  }
  legend(id, items, type, title) {
    const host = $(id);
    host.replaceChildren(el("strong", title));
    if (type === "shape" && items.length > SHAPES.length)
      host.append(
        el("p", `Symbols repeat after ${SHAPES.length} categories.`, "muted"),
      );
    for (const item of items) {
      const row = el("div", undefined, "channel-key"),
        canvas = el("canvas");
      canvas.width = 30;
      canvas.height = 24;
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "#267d96";
      drawSymbol(ctx, 15, 12, type === "size" ? 4 * item.size : 6, item.shape);
      row.append(canvas, el("span", item.label));
      host.append(row);
    }
  }
  table() {
    const s = this.state.explorer,
      host = $("summary-rows");
    host.replaceChildren();
    $("clear-isolate").hidden = !s.isolate;
    if (!s.summary) return;
    for (const item of summary(this.state.cells, s.summary)) {
      const tr = el("tr"),
        td = el("td"),
        button = el("button", item.label);
      button.setAttribute(
        "aria-pressed",
        String(s.isolate?.key === s.summary && s.isolate.value === item.label),
      );
      button.onclick = () => {
        s.isolate =
          s.isolate?.key === s.summary && s.isolate.value === item.label
            ? null
            : { key: s.summary, value: item.label };
        this.change();
      };
      td.append(button);
      tr.append(
        td,
        el("td", String(item.count)),
        el("td", item.percent.toFixed(1) + "%"),
        el("td", String(item.visible)),
      );
      host.append(tr);
    }
  }
  addCategory() {
    const key = $("category-by").value;
    if (!key || this.state.explorer.categories.some((f) => f.key === key))
      return;
    this.state.explorer.categories.push({
      key,
      values: [
        ...new Set(this.state.cells.cells.map((c) => category(c.row[key]))),
      ],
    });
    this.filters();
    this.change();
  }
  addGene() {
    const key = $("filter-gene").value;
    if (!key || this.state.explorer.genes.some((f) => f.key === key)) return;
    if (this.state.explorer.genes.length >= 50) return;
    const info = buildCellColoring(this.state.cells, this.state.expression, {
      source: "gene",
      key,
    });
    if (!info.range) {
      $("filter-note").textContent =
        "This gene has no measured values in the loaded cells.";
      return;
    }
    this.state.explorer.genes.push({
      key,
      min: info.range[0],
      max: info.range[1],
    });
    this.filters();
    this.change();
  }
  filters() {
    const s = this.state.explorer,
      host = $("filter-list");
    host.replaceChildren();
    const card = (title, remove) => {
      const box = el("fieldset"),
        legend = el("legend", title),
        button = el("button", "Remove");
      button.onclick = remove;
      box.append(legend, button);
      host.append(box);
      return box;
    };
    for (const f of s.categories) {
      const box = card(f.key, () => {
        s.categories = s.categories.filter((x) => x !== f);
        this.filters();
        this.change();
      });
      const list = el("div", undefined, "category-toggles");
      for (const value of [
        ...new Set(this.state.cells.cells.map((c) => category(c.row[f.key]))),
      ].sort()) {
        const label = el("label"),
          check = el("input");
        check.type = "checkbox";
        check.checked = f.values.includes(value);
        check.onchange = () => {
          f.values = check.checked
            ? [...f.values, value]
            : f.values.filter((x) => x !== value);
          this.change();
        };
        label.append(check, document.createTextNode(value));
        list.append(label);
      }
      box.append(list);
    }
    for (const f of s.genes) {
      const box = card("Gene · " + f.key, () => {
          s.genes = s.genes.filter((x) => x !== f);
          this.filters();
          this.change();
        }),
        info = buildCellColoring(this.state.cells, this.state.expression, {
          source: "gene",
          key: f.key,
        }),
        hist = histogram(this.state.cells.cells.map(info.value)),
        canvas = el("canvas");
      canvas.width = 240;
      canvas.height = 70;
      canvas.className = "histogram";
      canvas.setAttribute("role", "img");
      canvas.setAttribute(
        "aria-label",
        `${f.key}: ${hist.count} measured cells; distribution before filters`,
      );
      box.append(canvas);
      const output = el("output");
      box.append(output);
      const inputs = [];
      const paint = () => {
        output.textContent = `${f.min} – ${f.max}`;
        const ctx = canvas.getContext("2d"),
          peak = Math.max(1, ...hist.bins);
        ctx.clearRect(0, 0, 240, 70);
        hist.bins.forEach((n, i) => {
          const value =
            hist.range[0] +
            ((hist.range[1] - hist.range[0]) * (i + 0.5)) / hist.bins.length;
          ctx.fillStyle =
            value >= f.min && value <= f.max ? "#168f91" : "#b5c3ce";
          ctx.fillRect(i * 10, 70 - (n / peak) * 64, 9, (n / peak) * 64);
        });
      };
      for (const key of ["min", "max"]) {
        const label = el(
            "label",
            key === "min" ? "Minimum expression" : "Maximum expression",
          ),
          range = el("input");
        range.type = "range";
        range.min = hist.range[0];
        range.max = hist.range[1];
        range.step =
          hist.range[0] === hist.range[1]
            ? "1"
            : String((hist.range[1] - hist.range[0]) / 1000);
        range.value = f[key];
        range.disabled = hist.range[0] === hist.range[1];
        range.setAttribute("aria-label", `${f.key} ${key}`);
        const number = el("input");
        number.type = "number";
        number.step = "any";
        number.value = f[key];
        number.setAttribute("aria-label", `${f.key} ${key} value`);
        const set = (value) => {
          if (!Number.isFinite(value)) return;
          f[key] =
            key === "min"
              ? Math.max(hist.range[0], Math.min(value, f.max))
              : Math.min(hist.range[1], Math.max(value, f.min));
          range.value = f[key];
          number.value = f[key];
          paint();
          this.change();
        };
        range.oninput = () => set(Number(range.value));
        number.onchange = () => set(Number(number.value));
        box.append(label, range, number);
        inputs.push(range);
      }
      paint();
    }
    $("filter-note").textContent =
      "All filters combine with AND. Missing expression is excluded by gene filters. Histograms show all measured cells before filtering.";
  }
  embedding() {
    const canvas = $("embedding"),
      ctx = canvas.getContext("2d"),
      s = this.state.explorer;
    ctx.clearRect(0, 0, 600, 360);
    this.points = [];
    if (!s?.embeddingX || !s?.embeddingY) return;
    const points = (this.state.cells?.cells || [])
      .filter((c) =>
        [s.embeddingX, s.embeddingY].every(
          (key) =>
            c.row[key] != null &&
            String(c.row[key]).trim() !== "" &&
            Number.isFinite(Number(c.row[key])),
        ),
      )
      .map((cell) => ({
        cell,
        x: Number(cell.row[s.embeddingX]),
        y: Number(cell.row[s.embeddingY]),
      }));
    if (!points.length) return;
    let xmin = Infinity,
      xmax = -Infinity,
      ymin = Infinity,
      ymax = -Infinity;
    for (const p of points) {
      xmin = Math.min(xmin, p.x);
      xmax = Math.max(xmax, p.x);
      ymin = Math.min(ymin, p.y);
      ymax = Math.max(ymax, p.y);
    }
    ctx.fillStyle = "#edf4f7";
    ctx.fillRect(0, 0, 600, 360);
    for (const p of points)
      if (p.cell.visible) {
        p.x = 30 + 540 * (xmax === xmin ? 0.5 : (p.x - xmin) / (xmax - xmin));
        p.y = 330 - 300 * (ymax === ymin ? 0.5 : (p.y - ymin) / (ymax - ymin));
        ctx.fillStyle = this.state.cellColor(p.cell);
        drawSymbol(
          ctx,
          p.x,
          p.y,
          3.5 * this.state.cellChannels.size(p.cell),
          this.state.cellChannels.shape(p.cell),
        );
        this.points.push(p);
      }
    ctx.fillStyle = "#27495c";
    ctx.font = "13px sans-serif";
    ctx.fillText(s.embeddingX, 30, 354);
    ctx.fillText(s.embeddingY, 8, 16);
    $("embedding-note").textContent =
      `${this.points.length} visible cells plotted · click a point to Locate. Axes use uploaded values; no embedding is calculated.`;
  }
}
