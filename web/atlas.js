import { gunzipSync } from "fflate";
import { validateMesh, geometryHash, centroids, FaceIndex } from "./core.js";
const base = new URL("data/", document.baseURI);
async function request(path) {
  const r = await fetch(new URL(path, base));
  if (!r.ok) throw Error(`Atlas download failed (${r.status}). Please retry.`);
  return r;
}
export async function loadManifest() {
  return (await request("atlas.json")).json();
}
export async function loadMesh(region) {
  const bytes = new Uint8Array(
    await (await request(region.file)).arrayBuffer(),
  );
  const raw = bytes[0] === 31 && bytes[1] === 139 ? gunzipSync(bytes) : bytes;
  const view = new DataView(raw.buffer, raw.byteOffset, raw.byteLength),
    nv = view.getUint32(0, true),
    nf = view.getUint32(4, true);
  if (raw.length !== 8 + nv * 24 + nf * 12)
    throw Error("Incomplete mesh data. Please retry.");
  const vertices = new Float64Array(nv * 3),
    faces = new Uint32Array(nf * 3);
  for (let i = 0; i < vertices.length; i++)
    vertices[i] = view.getFloat64(8 + i * 8, true);
  for (let i = 0; i < faces.length; i++)
    faces[i] = view.getUint32(8 + nv * 24 + i * 4, true);
  validateMesh(vertices, faces);
  if ((await geometryHash(vertices, faces)) !== region.mesh_geometry_sha256)
    throw Error("Mesh integrity check failed. Reload before painting.");
  const centers = centroids(vertices, faces);
  return {
    ...region,
    vertices,
    faces,
    centroids: centers,
    index: new FaceIndex(centers),
    painted: new Set(),
    mirrored: new Set(),
    visible: true,
    opacity: 0.8,
  };
}
export async function loadSlice(axis, index, width, height) {
  const bytes = new Uint8Array(
    await (await request(`slices/${axis}/${index}.bin.gz`)).arrayBuffer(),
  );
  const raw = bytes[0] === 31 && bytes[1] === 139 ? gunzipSync(bytes) : bytes;
  if (raw.length !== width * height * 4) throw Error("Incomplete atlas slice.");
  const view = new DataView(raw.buffer, raw.byteOffset, raw.byteLength),
    out = new Uint32Array(width * height);
  for (let i = 0; i < out.length; i++) out[i] = view.getUint32(i * 4, true);
  return out;
}
