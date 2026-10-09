import test from "node:test";
import assert from "node:assert/strict";
import { zipSync, strToU8 } from "fflate";
import {
  parseExpressionRows,
  matchExpression,
  buildCellColoring,
  MISSING_COLOR,
  validateExpression,
  mergeExpression,
} from "../expression.js";
import { projectData, validateProject } from "../export.js";
import { readProject, mergeProjects } from "../session.js";

const table = {
  units: "um",
  headers: ["cell_id", "x", "y", "z", "MECvsLEC"],
  cells: ["AM93", "AM94", "AM100", "AM103", "AM105", "AM109"].map(
    (cell_id, i) => ({
      row: { cell_id, x: i, y: 1, z: 2, MECvsLEC: i === 3 ? "MEC" : "LEC" },
      xyz: [i, 1, 2],
      visible: true,
    }),
  ),
};
const rows = [
  ["", "AM105", "AM93", "AM103", "extra"],
  ["GeneA", 2.03184, 0, 1.402177, 999],
  ["GeneB", "NA", 4, 0, 2],
];
const expression = () => parseExpressionRows(rows, table, "counts.csv");
const manifest = { atlas: "test", atlas_version: "3.1", regions: [] };
const project = () =>
  projectData({
    manifest,
    active: null,
    regions: new Map(),
    paintColor: "#ff795f",
    mirrorColor: "#55d9e7",
    cells: table,
    expression: expression(),
    coloring: { source: "gene", key: "GeneA" },
  });

test("expression matches IDs, preserves fractions and zero, excludes unmatched columns from the scale", () => {
  const data = expression(),
    match = matchExpression(data, table),
    colors = buildCellColoring(table, data, { source: "gene", key: "GeneA" });
  assert.equal(match.matched, 3);
  assert.deepEqual(match.unmatchedMetadata, ["AM94", "AM100", "AM109"]);
  assert.deepEqual(match.unmatchedExpression, ["extra"]);
  assert.deepEqual(table.cells.map(colors.value), [
    0,
    null,
    null,
    1.402177,
    2.03184,
    null,
  ]);
  assert.deepEqual(colors.range, [0, 2.03184]);
  assert.notEqual(colors.color(table.cells[0]), MISSING_COLOR);
  assert.equal(colors.color(table.cells[1]), MISSING_COLOR);
  const reordered = { ...table, cells: [...table.cells].reverse() };
  assert.deepEqual(
    reordered.cells.map(
      buildCellColoring(reordered, data, { source: "gene", key: "GeneA" })
        .value,
    ),
    [null, 2.03184, 1.402177, null, null, 0],
  );
});
test("one source controls colors; categorical metadata and missing gene values are distinct", () => {
  const data = expression(),
    meta = buildCellColoring(table, data, {
      source: "metadata",
      key: "MECvsLEC",
    });
  assert.deepEqual(
    meta.categories.map((x) => x.label),
    ["LEC", "MEC"],
  );
  assert.equal(meta.range, null);
  assert.equal(meta.color(table.cells[0]), meta.color(table.cells[4]));
  assert.notEqual(meta.color(table.cells[0]), meta.color(table.cells[3]));
  const gene = buildCellColoring(table, data, { source: "gene", key: "GeneB" });
  assert.equal(gene.value(table.cells[4]), null);
  assert.equal(gene.value(table.cells[3]), 0);
  assert.deepEqual(gene.categories, []);
  assert.equal(
    buildCellColoring(table, data, { source: "single", key: "" }).color(
      table.cells[4],
    ),
    "#16bda5",
  );
});
test("reject ambiguous IDs, malformed dimensions, duplicate genes and invalid values", () => {
  for (const [matrix, pattern] of [
    [
      [
        ["gene", "AM93", "AM93"],
        ["G", 1, 2],
      ],
      /Duplicate expression cell/,
    ],
    [
      [
        ["gene", "am93"],
        ["G", 1],
      ],
      /No cell IDs match/,
    ],
    [
      [
        ["gene", "AM93"],
        ["G", 1],
        ["G", 2],
      ],
      /Duplicate gene/,
    ],
    [
      [
        ["gene", "AM93"],
        ["G", 1, 2],
      ],
      /expected 1/,
    ],
    [
      [
        ["gene", "AM93"],
        ["G", "oops"],
      ],
      /Non-numeric/,
    ],
    [
      [
        ["gene", "AM93"],
        ["G", Infinity],
      ],
      /Non-numeric/,
    ],
  ])
    assert.throws(() => parseExpressionRows(matrix, table), pattern);
  assert.throws(
    () =>
      parseExpressionRows(rows, {
        ...table,
        cells: [table.cells[0], table.cells[0]],
      }),
    /Duplicate metadata/,
  );
  assert.throws(
    () => parseExpressionRows(rows, { ...table, headers: ["x"] }),
    /cell_id column/,
  );
  assert.equal(
    parseExpressionRows(
      [
        ["gene", " AM93 "],
        [" G ", 1],
      ],
      table,
    ).genes[0],
    "G",
  );
  const corrupt = expression();
  corrupt.values[0][0] = "2";
  assert.throws(
    () => validateExpression(corrupt, table),
    /Invalid saved expression values/,
  );
});
test("editable JSON and ZIP preserve matrix, selected gene and hidden cells; old projects remain readable", async () => {
  const p = JSON.parse(JSON.stringify(project()));
  p.cells.cells[0].visible = false;
  const saved = await readProject(
    new File([JSON.stringify(p)], "saved.json"),
    manifest,
  );
  assert.deepEqual(saved, p);
  const bytes = zipSync({ "project.json": strToU8(JSON.stringify(p)) });
  assert.deepEqual(
    await readProject(new File([bytes], "saved.zip"), manifest),
    p,
  );
  assert.equal(
    buildCellColoring(saved.cells, saved.expression, saved.coloring).value(
      saved.cells.cells[0],
    ),
    0,
  );
  p.coloring.key = "missing";
  assert.throws(() => validateProject(p, manifest), /Saved gene/);
  const old = project();
  old.version = 2;
  delete old.expression;
  delete old.coloring;
  old.colorColumn = "MECvsLEC";
  assert.equal(validateProject(old, manifest).version, 2);
});
test("combining expression preserves values and rejects conflicts and ambiguous merged metadata", () => {
  const a = expression(),
    b = {
      version: 1,
      sourceName: "b.csv",
      genes: ["GeneA", "New"],
      cellIds: ["new"],
      values: [[3], [7]],
    };
  const merged = mergeExpression(a, b);
  assert.deepEqual(merged.values[0], [2.03184, 0, 1.402177, 999, 3]);
  assert.deepEqual(merged.values[2], [null, null, null, null, 7]);
  const conflict = structuredClone(a);
  conflict.values[0][0] = 9;
  assert.throws(() => mergeExpression(a, conflict), /Conflicting expression/);
  assert.throws(
    () => mergeProjects(project(), project(), "duplicate.zip"),
    /Duplicate metadata/,
  );
});
