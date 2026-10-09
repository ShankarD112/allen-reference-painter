import { heatColor } from "./core.js";

export const MISSING_COLOR = "#8799a9";
export const MAX_EXPRESSION_VALUES = 5_000_000;
const PALETTE = [
  "#0072b2",
  "#d55e00",
  "#009e73",
  "#cc79a7",
  "#e69f00",
  "#56b4e9",
  "#8b5fbf",
  "#716252",
  "#d84773",
  "#31837a",
];
const id = (value) => String(value ?? "").trim();
const missing = (value) =>
  value === null ||
  value === undefined ||
  id(value) === "" ||
  /^(NA|NaN)$/i.test(id(value));
const range = (values) => {
  let min = Infinity,
    max = -Infinity;
  for (const v of values)
    if (v !== null && Number.isFinite(v)) {
      min = Math.min(min, v);
      max = Math.max(max, v);
    }
  return min === Infinity ? null : [min, max];
};

export function metadataIds(table) {
  const column = table?.headers.find(
    (h) => h.trim().toLowerCase() === "cell_id",
  );
  if (!column)
    throw Error(
      "Gene expression requires a cell_id column in the cell metadata.",
    );
  const ids = table.cells.map((c) => id(c.row[column])),
    seen = new Set();
  for (let i = 0; i < ids.length; i++) {
    if (!ids[i]) throw Error(`Missing cell_id in metadata data row ${i + 1}.`);
    if (seen.has(ids[i]))
      throw Error(
        `Duplicate metadata cell_id "${ids[i]}". Expression matching requires unique IDs; use Resume rather than combine duplicate cell tables.`,
      );
    seen.add(ids[i]);
  }
  return { column, ids };
}
export function matchExpression(expression, table) {
  const metadata = metadataIds(table),
    columns = new Set(expression.cellIds),
    cells = new Set(metadata.ids);
  const matched = metadata.ids.filter((x) => columns.has(x));
  if (!matched.length)
    throw Error(
      "No cell IDs match. Expression columns must match metadata cell_id exactly (case-sensitive; surrounding spaces are ignored).",
    );
  return {
    column: metadata.column,
    matched: matched.length,
    metadataTotal: metadata.ids.length,
    unmatchedMetadata: metadata.ids.filter((x) => !columns.has(x)),
    unmatchedExpression: expression.cellIds.filter((x) => !cells.has(x)),
  };
}
export function expressionBuilder(sourceName = "") {
  const data = { version: 1, sourceName, cellIds: [], genes: [], values: [] },
    genes = new Set();
  let header = false,
    rowNumber = 0;
  return {
    add(row) {
      rowNumber++;
      if (row.every((v) => v === null || v === undefined || id(v) === ""))
        return;
      if (!header) {
        if (row.length < 2)
          throw Error(
            "Expression file needs gene names in the first column and cell IDs across the header.",
          );
        data.cellIds = row.slice(1).map(id);
        const seen = new Set();
        for (const value of data.cellIds) {
          if (!value)
            throw Error("An expression column is missing its cell ID.");
          if (seen.has(value))
            throw Error(`Duplicate expression cell ID "${value}".`);
          seen.add(value);
        }
        header = true;
        return;
      }
      if (row.length !== data.cellIds.length + 1)
        throw Error(
          `Expression row ${rowNumber} has ${row.length - 1} values; expected ${data.cellIds.length}.`,
        );
      const gene = id(row[0]);
      if (!gene)
        throw Error(`Missing gene name in expression row ${rowNumber}.`);
      if (genes.has(gene))
        throw Error(`Duplicate gene "${gene}". Use unique gene names or IDs.`);
      if ((data.genes.length + 1) * data.cellIds.length > MAX_EXPRESSION_VALUES)
        throw Error(
          "Expression matrix exceeds 5 million values. Export a subset of cells or genes first.",
        );
      const values = row.slice(1).map((v, i) => {
        if (missing(v)) return null;
        if (typeof v === "boolean" || !Number.isFinite(Number(v)))
          throw Error(
            `Non-numeric expression for gene "${gene}", cell "${data.cellIds[i]}".`,
          );
        return Number(v);
      });
      genes.add(gene);
      data.genes.push(gene);
      data.values.push(values);
    },
    finish(table) {
      if (!data.genes.length) throw Error("Expression file has no gene rows.");
      matchExpression(data, table);
      return data;
    },
  };
}
export function parseExpressionRows(rows, table, sourceName = "") {
  const parser = expressionBuilder(sourceName);
  rows.forEach((row) => parser.add(row));
  return parser.finish(table);
}
export function validateExpression(data, table) {
  if (
    !data ||
    data.version !== 1 ||
    typeof data.sourceName !== "string" ||
    !Array.isArray(data.cellIds) ||
    !data.cellIds.length ||
    !Array.isArray(data.genes) ||
    !data.genes.length ||
    !Array.isArray(data.values) ||
    data.values.length !== data.genes.length ||
    data.genes.length * data.cellIds.length > MAX_EXPRESSION_VALUES
  )
    throw Error("Invalid or oversized saved expression matrix.");
  for (const values of [data.cellIds, data.genes]) {
    const seen = new Set();
    for (const v of values) {
      if (typeof v !== "string" || !v || v !== v.trim() || seen.has(v))
        throw Error("Saved expression names must be nonempty and unique.");
      seen.add(v);
    }
  }
  for (const row of data.values)
    if (
      !Array.isArray(row) ||
      row.length !== data.cellIds.length ||
      row.some(
        (v) => v !== null && (typeof v !== "number" || !Number.isFinite(v)),
      )
    )
      throw Error("Invalid saved expression values.");
  matchExpression(data, table);
  return data;
}
export function activeColoring(state) {
  return (
    state.coloring ??
    (state.colorColumn
      ? { source: "metadata", key: state.colorColumn }
      : { source: "single", key: "" })
  );
}
export function validateColoring(coloring, table, expression) {
  if (
    !coloring ||
    !["single", "metadata", "gene"].includes(coloring.source) ||
    typeof coloring.key !== "string"
  )
    throw Error("Invalid saved cell coloring.");
  if (coloring.source === "metadata" && !table?.headers.includes(coloring.key))
    throw Error("Saved metadata color column is missing.");
  if (coloring.source === "gene" && !expression?.genes.includes(coloring.key))
    throw Error("Saved gene coloring has no matching expression data.");
}
export function buildCellColoring(table, expression, coloring) {
  if (!table || coloring.source === "single")
    return {
      source: "single",
      key: "",
      label: "Single color",
      range: null,
      categories: [],
      missing: 0,
      color: () => "#16bda5",
      value: () => null,
    };
  validateColoring(coloring, table, expression);
  let values;
  if (coloring.source === "gene") {
    const { column } = metadataIds(table),
      row = expression.values[expression.genes.indexOf(coloring.key)],
      map = new Map(expression.cellIds.map((x, i) => [x, i]));
    values = table.cells.map((c) => {
      const index = map.get(id(c.row[column]));
      return index === undefined ? null : row[index];
    });
  } else
    values = table.cells.map((c) =>
      missing(c.row[coloring.key]) ? null : c.row[coloring.key],
    );
  const numeric =
    coloring.source === "gene" ||
    values
      .filter((v) => v !== null)
      .every((v) => typeof v !== "boolean" && Number.isFinite(Number(v)));
  if (numeric) values = values.map((v) => (v === null ? null : Number(v)));
  else values = values.map((v) => (v === null ? null : String(v)));
  const index = new Map(table.cells.map((c, i) => [c, i])),
    extent = numeric ? range(values) : null;
  const categories = numeric
    ? []
    : [...new Set(values.filter((v) => v !== null))]
        .sort((a, b) => a.localeCompare(b))
        .map((label, i) => ({
          label,
          color:
            i < PALETTE.length
              ? PALETTE[i]
              : `hsl(${(i * 137.508) % 360} 55% 43%)`,
        }));
  const colors = new Map(categories.map((c) => [c.label, c.color]));
  const value = (cell) => values[index.get(cell)] ?? null;
  return {
    source: coloring.source,
    key: coloring.key,
    label: `${coloring.source === "gene" ? "Gene" : "Metadata"} · ${coloring.key}`,
    range: extent,
    categories,
    missing: values.filter((v) => v === null).length,
    value,
    color: (cell) => {
      const v = value(cell);
      return v === null
        ? MISSING_COLOR
        : numeric
          ? heatColor(v, extent)
          : colors.get(v);
    },
  };
}
// Combine disjoint cell tables; reject contradictory values rather than silently overwrite.
export function mergeExpression(left, right) {
  if (!left) return right ? structuredClone(right) : null;
  if (!right) return structuredClone(left);
  const cellIds = [...new Set([...left.cellIds, ...right.cellIds])],
    genes = [...new Set([...left.genes, ...right.genes])];
  if (cellIds.length * genes.length > MAX_EXPRESSION_VALUES)
    throw Error("Combined expression matrix exceeds 5 million values.");
  const positions = new Map(cellIds.map((x, i) => [x, i])),
    genePositions = new Map(genes.map((x, i) => [x, i])),
    values = genes.map(() => Array(cellIds.length).fill(null));
  for (const input of [left, right])
    for (let g = 0; g < input.genes.length; g++)
      for (let c = 0; c < input.cellIds.length; c++) {
        const v = input.values[g][c];
        if (v === null) continue;
        const row = values[genePositions.get(input.genes[g])],
          pos = positions.get(input.cellIds[c]);
        if (row[pos] !== null && row[pos] !== v)
          throw Error(
            `Conflicting expression for ${input.genes[g]} / ${input.cellIds[c]}.`,
          );
        row[pos] = v;
      }
  return {
    version: 1,
    sourceName: "Combined expression tables",
    cellIds,
    genes,
    values,
  };
}
