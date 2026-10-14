import test from "node:test";
import assert from "node:assert/strict";
import {
  defaults,
  colorEncoding,
  channels,
  applyFilters,
  summary,
  histogram,
  validateExplorer,
  interpolate,
  SCALES,
} from "../cell-explorer.js";
import { parseExpressionRows } from "../expression.js";
import { projectData, validateProject } from "../export.js";
const manifest = { atlas: "test", atlas_version: "3.1", regions: [] };
function state() {
  const cells = {
    units: "um",
    headers: ["cell_id", "x", "y", "z", "Group", "Score"],
    cells: ["a", "b", "c", "d"].map((id, i) => ({
      row: {
        cell_id: id,
        x: i,
        y: 1,
        z: 2,
        Group: i < 2 ? "A" : "B",
        Score: i,
      },
      xyz: [i, 1, 2],
      visible: true,
    })),
  };
  return {
    manifest,
    active: null,
    paintColor: "#ff795f",
    mirrorColor: "#55d9e7",
    regions: new Map(),
    cells,
    expression: parseExpressionRows(
      [
        ["gene", "d", "b", "a"],
        ["G", 9, 3, 0],
        ["H", 1, 4, 2],
      ],
      cells,
    ),
    coloring: { source: "gene", key: "G" },
    explorer: defaults(),
    dataSource: { name: "cells.csv", kind: "upload" },
  };
}
test("scales clamp display colors without changing values and retain missing gray", () => {
  const s = state();
  Object.assign(s.explorer, { palette: "grayscale", min: 2, max: 5 });
  const c = colorEncoding(s);
  assert.equal(c.color(s.cells.cells[0]), SCALES.grayscale[0]);
  assert.equal(c.color(s.cells.cells[3]), SCALES.grayscale[1]);
  assert.equal(c.value(s.cells.cells[0]), 0);
  assert.equal(c.color(s.cells.cells[2]), "#8799a9");
  assert.deepEqual(c.range, [2, 5]);
  s.explorer.palette = "custom";
  s.explorer.custom = ["#000000", "#ffffff", "#ff0000"];
  s.explorer.customCount = 2;
  assert.equal(colorEncoding(s).color(s.cells.cells[3]), "#ffffff");
  assert.equal(interpolate(["#000000", "#ffffff"], 0.5), "#808080");
});
test("category and multiple gene ranges combine with AND without erasing manual visibility", () => {
  const s = state();
  s.cells.cells[0].visible = false;
  s.explorer.genes = [
    { key: "G", min: 0, max: 9 },
    { key: "H", min: 2, max: 4 },
  ];
  applyFilters(s);
  assert.deepEqual(
    s.cells.cells.map((c) => c.visible),
    [false, true, false, false],
  );
  s.explorer.categories = [{ key: "Group", values: ["B"] }];
  applyFilters(s);
  assert.equal(s.cells.cells.filter((c) => c.visible).length, 0);
  s.explorer = defaults();
  applyFilters(s);
  assert.deepEqual(
    s.cells.cells.map((c) => c.visible),
    [false, true, true, true],
  );
});
test("shape and size are independent channels with stable missing-size behavior", () => {
  const s = state();
  s.explorer.shape = "Group";
  s.explorer.size = { source: "gene", key: "G" };
  const c = channels(s);
  assert.notEqual(c.shape(s.cells.cells[0]), c.shape(s.cells.cells[3]));
  assert.equal(c.size(s.cells.cells[2]), 0.7);
  assert.ok(c.size(s.cells.cells[0]) < c.size(s.cells.cells[3]));
  assert.equal(c.shapeLegend.length, 2);
  assert.ok(c.sizeLegend.some((x) => x.label === "Missing"));
});
test("summary uses loaded total; isolation is reversible and histogram excludes missing, retains zero", () => {
  const s = state();
  s.explorer.isolate = { key: "Group", value: "A" };
  applyFilters(s);
  assert.deepEqual(
    summary(s.cells, "Group").map((x) => [x.count, x.percent, x.visible]),
    [
      [2, 50, 2],
      [2, 50, 0],
    ],
  );
  const h = histogram([0, 0, 9, null]);
  assert.equal(h.count, 3);
  assert.deepEqual(h.range, [0, 9]);
  assert.equal(h.bins[0], 2);
  assert.equal(histogram([0, 0]).bins[0], 2);
  s.explorer.isolate = null;
  applyFilters(s);
  assert.ok(s.cells.cells.every((c) => c.visible));
});
test("project round trip retains provenance, filters, encodings and manual visibility; rejects invalid ranges", () => {
  const s = state();
  s.explorer.genes = [{ key: "G", min: 0, max: 4 }];
  s.explorer.shape = "Group";
  applyFilters(s);
  const p = JSON.parse(JSON.stringify(projectData(s)));
  validateProject(p, manifest);
  assert.equal(p.version, 4);
  assert.equal(p.dataSource.name, "cells.csv");
  assert.equal(p.cells.cells[3].manualVisible, true);
  assert.equal(p.cells.cells[3].visible, false);
  p.explorer.genes[0].key = "absent";
  assert.throws(() => validateProject(p, manifest), /gene filter/);
  assert.throws(
    () =>
      validateExplorer(
        { ...defaults(), min: 5, max: 1 },
        s.cells,
        s.expression,
      ),
    /clipping/,
  );
});
