import {
  buildCellColoring,
  activeColoring,
  validateColoring,
} from "./expression.js";
export const SCALES = {
  legacy: ["#2c70b4", "#3dd1be", "#ffd966"],
  viridis: ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"],
  magma: ["#000004", "#51127c", "#b73779", "#fc8961", "#fcfdbf"],
  plasma: ["#0d0887", "#7e03a8", "#cc4778", "#f89540", "#f0f921"],
  "red-blue": ["#b2182b", "#f7f7f7", "#2166ac"],
  grayscale: ["#161616", "#f5f5f5"],
};
export const SHAPES = ["circle", "square", "triangle", "diamond", "cross"];
export const DEFAULT_EXPLORER = {
  palette: "viridis",
  custom: ["#440154", "#21918c", "#fde725"],
  customCount: 3,
  min: null,
  max: null,
  shape: "",
  size: null,
  categories: [],
  genes: [],
  summary: "",
  isolate: null,
  embeddingX: "",
  embeddingY: "",
};
export const defaults = () => structuredClone(DEFAULT_EXPLORER);
export const absent = (v) =>
  v == null || String(v).trim() === "" || /^(na|nan)$/i.test(String(v).trim());
export const category = (v) => (absent(v) ? "(missing)" : String(v));
export function variableType(table, key) {
  const values = table.cells.map((c) => c.row[key]).filter((v) => !absent(v));
  return values.length &&
    values.every((v) => typeof v !== "boolean" && Number.isFinite(Number(v)))
    ? "continuous"
    : "categorical";
}
export function variables(state) {
  return [
    ...(state.cells?.headers || []).map((key) => ({
      source: "metadata",
      key,
      type: variableType(state.cells, key),
    })),
    ...(state.expression?.genes || []).map((key) => ({
      source: "gene",
      key,
      type: "continuous",
    })),
  ];
}
export const token = (variable) =>
  variable ? JSON.stringify([variable.source, variable.key]) : "";
export const fromToken = (value) => {
  if (!value) return null;
  const [source, key] = JSON.parse(value);
  return { source, key };
};
export function interpolate(stops, t) {
  const position = Math.max(0, Math.min(1, t)) * (stops.length - 1),
    i = Math.min(stops.length - 2, Math.floor(position)),
    f = position - i;
  const rgb = (hex) =>
    hex
      .slice(1)
      .match(/../g)
      .map((x) => parseInt(x, 16));
  return (
    "#" +
    rgb(stops[i])
      .map((x, j) =>
        Math.round(x + (rgb(stops[i + 1])[j] - x) * f)
          .toString(16)
          .padStart(2, "0"),
      )
      .join("")
  );
}
export function colorEncoding(state) {
  const info = buildCellColoring(
      state.cells,
      state.expression,
      activeColoring(state),
    ),
    settings = state.explorer || defaults();
  if (!info.range) return info;
  const stops =
    settings.palette === "custom"
      ? settings.custom.slice(0, settings.customCount)
      : SCALES[settings.palette] || SCALES.viridis;
  const range = [settings.min ?? info.range[0], settings.max ?? info.range[1]];
  if (range[0] > range[1])
    throw Error("Color minimum must not exceed maximum.");
  return {
    ...info,
    dataRange: info.range,
    range,
    stops,
    color: (cell) => {
      const v = info.value(cell);
      return v === null
        ? "#8799a9"
        : interpolate(
            stops,
            range[1] === range[0]
              ? 0.5
              : (v - range[0]) / (range[1] - range[0]),
          );
    },
  };
}
export function channels(state) {
  const settings = state.explorer || defaults(),
    cells = state.cells?.cells || [];
  const labels = settings.shape
    ? [...new Set(cells.map((c) => category(c.row[settings.shape])))].sort()
    : [];
  const shapeMap = new Map(
    labels.map((label, i) => [label, SHAPES[i % SHAPES.length]]),
  );
  const sizeInfo = settings.size
    ? buildCellColoring(state.cells, state.expression, settings.size)
    : null;
  const sizeLabels = sizeInfo?.categories.map((c) => c.label) || [];
  const size = (cell) => {
    if (!sizeInfo) return 1;
    const v = sizeInfo.value(cell);
    if (v === null) return 0.7;
    if (sizeInfo.range) {
      const [lo, hi] = sizeInfo.range;
      return hi === lo ? 1.25 : 0.65 + (1.35 * (v - lo)) / (hi - lo);
    }
    return (
      0.65 + (1.35 * sizeLabels.indexOf(v)) / Math.max(1, sizeLabels.length - 1)
    );
  };
  const sizeLegend = !sizeInfo
    ? []
    : sizeInfo.range
      ? [
          ...new Set([
            sizeInfo.range[0],
            (sizeInfo.range[0] + sizeInfo.range[1]) / 2,
            sizeInfo.range[1],
          ]),
        ].map((v) => ({
          label: String(v),
          size:
            sizeInfo.range[1] === sizeInfo.range[0]
              ? 1.25
              : 0.65 +
                (1.35 * (v - sizeInfo.range[0])) /
                  (sizeInfo.range[1] - sizeInfo.range[0]),
        }))
      : sizeLabels.map((label, i) => ({
          label,
          size: 0.65 + (1.35 * i) / Math.max(1, sizeLabels.length - 1),
        }));
  if (sizeInfo?.missing) sizeLegend.push({ label: "Missing", size: 0.7 });
  return {
    shape: (cell) =>
      shapeMap.get(category(cell.row[settings.shape])) || "circle",
    size,
    shapeLegend: labels.map((label) => ({ label, shape: shapeMap.get(label) })),
    sizeLegend,
  };
}
export function applyFilters(state) {
  const s = state.explorer || defaults(),
    geneFilters = s.genes.map((f) => ({
      filter: f,
      info: buildCellColoring(state.cells, state.expression, {
        source: "gene",
        key: f.key,
      }),
    }));
  for (const cell of state.cells?.cells || []) {
    cell.manualVisible ??= cell.visible;
    cell.visible =
      cell.manualVisible &&
      s.categories.every((f) => f.values.includes(category(cell.row[f.key]))) &&
      (!s.isolate || category(cell.row[s.isolate.key]) === s.isolate.value) &&
      geneFilters.every(({ filter, info }) => {
        const v = info.value(cell);
        return v !== null && v >= filter.min && v <= filter.max;
      });
  }
}
export function summary(table, key) {
  const counts = new Map();
  for (const c of table?.cells || []) {
    const label = category(c.row[key]);
    const item = counts.get(label) || { label, count: 0, visible: 0 };
    item.count++;
    if (c.visible) item.visible++;
    counts.set(label, item);
  }
  return [...counts.values()]
    .sort((a, b) => a.label.localeCompare(b.label))
    .map((item) => ({
      ...item,
      percent: (100 * item.count) / table.cells.length,
    }));
}
export function histogram(values, bins = 24) {
  values = values.filter((v) => v !== null && Number.isFinite(v));
  if (!values.length) return { range: null, bins: [], count: 0 };
  let min = Infinity,
    max = -Infinity;
  for (const v of values) {
    min = Math.min(min, v);
    max = Math.max(max, v);
  }
  const counts = Array(bins).fill(0);
  for (const v of values)
    counts[
      min === max
        ? 0
        : Math.min(bins - 1, Math.floor(((v - min) / (max - min)) * bins))
    ]++;
  return { range: [min, max], bins: counts, count: values.length };
}
export function drawSymbol(ctx, x, y, r, shape = "circle") {
  ctx.beginPath();
  if (shape === "square") ctx.rect(x - r, y - r, 2 * r, 2 * r);
  else if (shape === "triangle") {
    ctx.moveTo(x, y - r);
    ctx.lineTo(x + r, y + r);
    ctx.lineTo(x - r, y + r);
    ctx.closePath();
  } else if (shape === "diamond") {
    ctx.moveTo(x, y - r);
    ctx.lineTo(x + r, y);
    ctx.lineTo(x, y + r);
    ctx.lineTo(x - r, y);
    ctx.closePath();
  } else if (shape === "cross") {
    ctx.rect(x - r, y - r / 3, r * 2, (r * 2) / 3);
    ctx.rect(x - r / 3, y - r, (r * 2) / 3, r * 2);
  } else ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();
}
export function validateExplorer(settings, table, expression) {
  if (!settings || typeof settings !== "object")
    throw Error("Invalid cell explorer settings.");
  const s = { ...defaults(), ...settings };
  if (
    ![...Object.keys(SCALES), "custom"].includes(s.palette) ||
    ![2, 3].includes(s.customCount) ||
    !Array.isArray(s.custom) ||
    s.custom.length !== 3 ||
    s.custom.some((c) => !/^#[0-9a-f]{6}$/i.test(c))
  )
    throw Error("Invalid color scale.");
  if (
    [s.min, s.max].some((v) => v !== null && !Number.isFinite(v)) ||
    (s.min !== null && s.max !== null && s.min > s.max)
  )
    throw Error("Invalid color clipping range.");
  for (const key of ["shape", "summary", "embeddingX", "embeddingY"])
    if (
      typeof s[key] !== "string" ||
      (s[key] && !table?.headers.includes(s[key]))
    )
      throw Error("Missing explorer metadata field.");
  if (s.shape && variableType(table, s.shape) !== "categorical")
    throw Error("Shape requires categorical metadata.");
  for (const key of ["embeddingX", "embeddingY"])
    if (s[key] && variableType(table, s[key]) !== "continuous")
      throw Error("Embedding axes must be numeric.");
  if (s.size) validateColoring(s.size, table, expression);
  if (
    !Array.isArray(s.categories) ||
    !Array.isArray(s.genes) ||
    s.genes.length > 50
  )
    throw Error("Invalid cell filters.");
  for (const f of s.categories)
    if (
      !table?.headers.includes(f.key) ||
      !Array.isArray(f.values) ||
      f.values.some((x) => typeof x !== "string")
    )
      throw Error("Invalid category filter.");
  for (const f of s.genes)
    if (
      !expression?.genes.includes(f.key) ||
      !Number.isFinite(f.min) ||
      !Number.isFinite(f.max) ||
      f.min > f.max
    )
      throw Error("Invalid gene filter.");
  if (
    s.isolate &&
    (!table?.headers.includes(s.isolate.key) ||
      typeof s.isolate.value !== "string")
  )
    throw Error("Invalid summary selection.");
  return s;
}
