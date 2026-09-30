// Scientific data stays in BrainGlobe AP/DV/ML micrometres. Rendering transforms
// are deliberately separate so camera/view changes never affect exports.
export const ALIASES = [
  ["x", "x_um", "atlas_x", "ap", "ap_um"],
  ["y", "y_um", "atlas_y", "dv", "dv_um"],
  ["z", "z_um", "atlas_z", "ml", "ml_um"],
];
export function toDisplay(p) {
  return [(p[2] - 5700) / 1000, (4000 - p[1]) / 1000, (6600 - p[0]) / 1000];
}
export function fromDisplay(p) {
  return [6600 - p[2] * 1000, 4000 - p[1] * 1000, 5700 + p[0] * 1000];
}
export function mirrorPoint(p, midline) {
  return [p[0], p[1], 2 * midline - p[2]];
}
export function centroids(vertices, faces) {
  const out = new Float64Array(faces.length);
  for (let i = 0; i < faces.length; i += 3)
    for (let a = 0; a < 3; a++)
      out[i + a] =
        (vertices[faces[i] * 3 + a] +
          vertices[faces[i + 1] * 3 + a] +
          vertices[faces[i + 2] * 3 + a]) /
        3;
  return out;
}
export class FaceIndex {
  constructor(points, size = 250) {
    this.points = points;
    this.size = size;
    this.bins = new Map();
    for (let i = 0; i < points.length; i += 3) {
      const k = this.key(points.slice(i, i + 3));
      if (!this.bins.has(k)) this.bins.set(k, []);
      this.bins.get(k).push(i / 3);
    }
  }
  key(p) {
    return Array.from(p, (x) => Math.floor(x / this.size)).join(",");
  }
  near(p, r) {
    const ids = [],
      n = this.points,
      s = this.size,
      low = p.map((x) => Math.floor((x - r) / s)),
      high = p.map((x) => Math.floor((x + r) / s));
    for (let x = low[0]; x <= high[0]; x++)
      for (let y = low[1]; y <= high[1]; y++)
        for (let z = low[2]; z <= high[2]; z++)
          for (const id of this.bins.get(`${x},${y},${z}`) || []) {
            let d = 0;
            for (let a = 0; a < 3; a++) d += (n[id * 3 + a] - p[a]) ** 2;
            if (d <= r * r) ids.push(id);
          }
    if (!ids.length) {
      let best = Infinity,
        id = -1;
      for (let i = 0; i < n.length; i += 3) {
        const d =
          (n[i] - p[0]) ** 2 + (n[i + 1] - p[1]) ** 2 + (n[i + 2] - p[2]) ** 2;
        if (d < best) {
          best = d;
          id = i / 3;
        }
      }
      if (id >= 0) ids.push(id);
    }
    return ids;
  }
}
export function parseCells(rows, units, resolution) {
  if (!["um", "mm", "voxel"].includes(units))
    throw Error("Choose the source coordinate units.");
  if (!rows.length) throw Error("The table has no data rows.");
  const headers = Object.keys(rows[0]);
  const axes = ALIASES.map((names) =>
    headers.find((h) => names.includes(h.trim().toLowerCase())),
  );
  if (axes.some((x) => !x))
    throw Error(
      "Coordinate columns are missing. Use AP / DV / ML or x / y / z.",
    );
  const invalid = [],
    cells = rows.map((row, i) => {
      const xyz = axes.map((h, a) => {
        const v = row[h];
        return (
          (v === null || v === undefined || String(v).trim() === ""
            ? NaN
            : Number(v)) *
          (units === "mm" ? 1000 : units === "voxel" ? resolution[a] : 1)
        );
      });
      if (!xyz.every(Number.isFinite)) invalid.push(i + 1);
      return { row, xyz, visible: true };
    });
  if (invalid.length)
    throw Error(
      `Invalid coordinates in data row${invalid.length > 1 ? "s" : ""}: ${invalid.slice(0, 20).join(", ")}${invalid.length > 20 ? "…" : ""}. No rows were imported.`,
    );
  return { headers, cells, units };
}
export function numericRange(cells, key) {
  const values = cells
    .map((c) => c.row[key])
    .filter((v) => v !== null && v !== undefined && String(v).trim() !== "")
    .map(Number)
    .filter(Number.isFinite);
  if (!values.length) return null;
  let min = Infinity,
    max = -Infinity;
  for (const v of values) {
    min = Math.min(min, v);
    max = Math.max(max, v);
  }
  return [min, max];
}
export function heatColor(v, range) {
  if (
    v === null ||
    v === undefined ||
    String(v).trim() === "" ||
    !Number.isFinite(Number(v)) ||
    !range
  )
    return "#8799a9";
  const t =
    range[1] === range[0]
      ? 0.5
      : Math.max(
          0,
          Math.min(1, (Number(v) - range[0]) / (range[1] - range[0])),
        );
  const stops = [
      [44, 112, 180],
      [61, 209, 190],
      [255, 217, 102],
    ],
    s = t < 0.5 ? 0 : 1,
    f = t < 0.5 ? t * 2 : (t - 0.5) * 2;
  return (
    "#" +
    stops[s]
      .map((v, i) =>
        Math.round(v + (stops[s + 1][i] - v) * f)
          .toString(16)
          .padStart(2, "0"),
      )
      .join("")
  );
}
export function csv(rows) {
  return (
    rows
      .map((r) =>
        r
          .map((v) => '"' + String(v ?? "").replaceAll('"', '""') + '"')
          .join(","),
      )
      .join("\r\n") + "\r\n"
  );
}
export function ply(vertices, faces, ids = null) {
  const selected = ids ?? Array.from({ length: faces.length / 3 }, (_, i) => i),
    used = [
      ...new Set(
        selected.flatMap((i) => Array.from(faces.slice(i * 3, i * 3 + 3))),
      ),
    ].sort((a, b) => a - b),
    map = new Map(used.map((id, i) => [id, i]));
  return (
    [
      "ply",
      "format ascii 1.0",
      "comment BrainGlobe AP DV ML in micrometres",
      `element vertex ${used.length}`,
      "property double x",
      "property double y",
      "property double z",
      `element face ${selected.length}`,
      "property list uchar int vertex_indices",
      "end_header",
      ...used.map((i) =>
        Array.from(vertices.slice(i * 3, i * 3 + 3)).join(" "),
      ),
      ...selected.map(
        (i) =>
          "3 " +
          Array.from(faces.slice(i * 3, i * 3 + 3), (id) => map.get(id)).join(
            " ",
          ),
      ),
    ].join("\n") + "\n"
  );
}
export async function geometryHash(vertices, faces) {
  const bytes = new Uint8Array(vertices.length * 8 + faces.length * 8),
    view = new DataView(bytes.buffer);
  vertices.forEach((v, i) => view.setFloat64(i * 8, v, true));
  faces.forEach((v, i) =>
    view.setBigInt64(vertices.length * 8 + i * 8, BigInt(v), true),
  );
  return [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
    .map((x) => x.toString(16).padStart(2, "0"))
    .join("");
}
export function validateMesh(vertices, faces) {
  if (
    !vertices.length ||
    vertices.length % 3 ||
    !faces.length ||
    faces.length % 3
  )
    throw Error("Invalid triangle geometry.");
  for (const x of vertices)
    if (!Number.isFinite(x)) throw Error("Nonfinite mesh coordinates.");
  for (const x of faces)
    if (!Number.isInteger(x) || x < 0 || x >= vertices.length / 3)
      throw Error("Invalid face index.");
}
