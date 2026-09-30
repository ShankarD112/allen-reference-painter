import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import {
  toDisplay,
  fromDisplay,
  mirrorPoint,
  centroids,
  FaceIndex,
  parseCells,
  numericRange,
  geometryHash,
  ply,
  csv,
} from "../core.js";
import { validateProject } from "../export.js";
const manifest = JSON.parse(readFileSync("public/data/atlas.json"));
const ent = manifest.regions.find((r) => r.acronym === "ENT");
const b = gunzipSync(readFileSync("public/data/" + ent.file));
const nv = b.readUInt32LE(0),
  nf = b.readUInt32LE(4),
  v = new Float64Array(nv * 3),
  f = new Uint32Array(nf * 3);
for (let i = 0; i < v.length; i++) v[i] = b.readDoubleLE(8 + i * 8);
for (let i = 0; i < f.length; i++) f[i] = b.readUInt32LE(8 + nv * 24 + i * 4);
const centers = centroids(v, f);
test("atlas coordinates roundtrip through display and mirror", () => {
  for (const p of [
    [0, 0, 0],
    [13200, 8000, 11400],
    [8432.5, 2181, 4193],
  ]) {
    fromDisplay(toDisplay(p)).forEach((x, i) =>
      assert.ok(Math.abs(x - p[i]) < 1e-9),
    );
    assert.deepEqual(mirrorPoint(mirrorPoint(p, 5700), 5700), p);
  }
});
test("real ENT geometry retains original Python-compatible hash", async () => {
  assert.equal(await geometryHash(v, f), ent.mesh_geometry_sha256);
  assert.equal(nf, ent.triangles);
});
test("indexed brush equals brute-force original centroid selection", () => {
  const index = new FaceIndex(centers);
  for (const face of [0, 50, 1000, nf - 1]) {
    const point = Array.from(centers.slice(face * 3, face * 3 + 3)),
      r = 250;
    const expected = [];
    for (let i = 0; i < nf; i++) {
      let d = 0;
      for (let a = 0; a < 3; a++) d += (centers[i * 3 + a] - point[a]) ** 2;
      if (d <= r * r) expected.push(i);
    }
    assert.deepEqual(
      index.near(point, r).sort((a, b) => a - b),
      expected,
    );
  }
  assert.deepEqual(
    new FaceIndex(new Float64Array([0, 0, 0, 2, 0, 0])).near([1, 0, 0], 0.1),
    [0],
  );
});
test("cell conversions are explicit and invalid rows reject whole import", () => {
  const rows = [{ AP: "1", DV: "2", ML: "3", Name: "Example" }];
  assert.deepEqual(
    parseCells(rows, "mm", [25, 25, 25]).cells[0].xyz,
    [1000, 2000, 3000],
  );
  assert.deepEqual(
    parseCells(rows, "voxel", [25, 25, 25]).cells[0].xyz,
    [25, 50, 75],
  );
  assert.throws(() => parseCells(rows, "", [25, 25, 25]));
  assert.throws(
    () => parseCells([...rows, { AP: "", DV: 2, ML: 3 }], "um", [25, 25, 25]),
    /row: 2/,
  );
  assert.deepEqual(
    numericRange(
      [{ row: { x: null } }, { row: { x: "2" } }, { row: { x: "9" } }],
      "x",
    ),
    [2, 9],
  );
});
test("project import rejects mismatched meshes and bad face IDs", () => {
  const p = {
    format: "allen-reference-painter-project",
    version: 1,
    atlas: manifest.atlas,
    atlas_version: manifest.atlas_version,
    active: ent.id,
    paintColor: "#ff795f",
    mirrorColor: "#55d9e7",
    cells: null,
    regions: [
      {
        id: ent.id,
        mesh_geometry_sha256: ent.mesh_geometry_sha256,
        painted: [0, 1],
        mirrored: [1],
        visible: true,
        opacity: 0.8,
      },
    ],
  };
  assert.equal(validateProject(p, manifest), p);
  assert.throws(() =>
    validateProject(
      { ...p, regions: [{ ...p.regions[0], painted: [nf] }] },
      manifest,
    ),
  );
  assert.throws(() =>
    validateProject(
      { ...p, regions: [{ ...p.regions[0], mesh_geometry_sha256: "bad" }] },
      manifest,
    ),
  );
});
test("real ROI export fixture for the existing Python validator", () => {
  const ids = new FaceIndex(centers)
    .near(Array.from(centers.slice(150, 153)), 250)
    .sort((a, b) => a - b);
  mkdirSync("test-results/coordinate-export", { recursive: true });
  writeFileSync("test-results/coordinate-export/ENT.ply", ply(v, f, ids));
  writeFileSync(
    "test-results/coordinate-export/ENT.csv",
    csv([
      ["area", "face_id", "center_x_um", "center_y_um", "center_z_um"],
      ...ids.map((id) => ["ENT", id, ...centers.slice(id * 3, id * 3 + 3)]),
    ]),
  );
  writeFileSync(
    "test-results/coordinate-export/ENT_metadata.json",
    JSON.stringify({
      atlas: manifest.atlas,
      atlas_version: manifest.atlas_version,
      atlas_resolution_um: manifest.atlas_resolution_um,
      atlas_shape: manifest.atlas_shape,
      mesh_geometry_sha256: ent.mesh_geometry_sha256,
      coordinate_units: "um",
      axis_order: ["AP", "DV", "ML"],
      ply_file: "ENT.ply",
      face_ids_file: "ENT.csv",
      n_painted_faces: ids.length,
    }),
  );
  assert.ok(ids.length > 0);
});
