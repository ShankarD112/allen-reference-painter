import test from "node:test";
import assert from "node:assert/strict";
import { cellLabel, nearestCell } from "../cell-hover.js";
test("cell ID is preferred; selected labels and row numbers provide fallbacks", () => {
  const cell = { row: { cell_id: "<AM93>", Name: "Sample" }, visible: true };
  const state = {
    cells: { headers: ["cell_id", "Name"], cells: [cell] },
    labelColumn: "Name",
  };
  assert.equal(cellLabel(cell, state), "cell_id: <AM93>");
  delete cell.row.cell_id;
  assert.equal(cellLabel(cell, state), "Sample");
  state.labelColumn = "";
  assert.equal(cellLabel(cell, state), "Cell 1");
});
test("cell hit testing uses nearest visible cell and screen-space distance", () => {
  const a = { visible: true },
    b = { visible: true },
    hidden = { visible: false };
  const points = [
    { cell: hidden, x: 10, y: 10 },
    { cell: a, x: 12, y: 10 },
    { cell: b, x: 20, y: 10, radius: 12 },
  ];
  assert.equal(nearestCell(points, 10, 10), a);
  assert.equal(nearestCell(points, 31, 10), b);
  assert.equal(nearestCell(points, 100, 100), null);
  a.visible = false;
  b.visible = false;
  assert.equal(nearestCell(points, 10, 10), null);
});
