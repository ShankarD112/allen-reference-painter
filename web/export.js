import { zipSync, strToU8 } from "fflate";
import { csv, ply, geometryHash } from "./core.js";
export function download(data, name, type = "application/octet-stream") {
  const url =
    typeof data === "string" && data.startsWith("data:")
      ? data
      : URL.createObjectURL(new Blob([data], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  if (url.startsWith("blob:"))
    setTimeout(() => URL.revokeObjectURL(url), 10000);
}
export async function exportAnalysis(state, activeOnly) {
  const atlas = state.manifest,
    regions = activeOnly
      ? [state.regions.get(state.active)]
      : [...state.regions.values()];
  if (!regions.length || !regions[0]) throw Error("Load a region first.");
  if (activeOnly && !regions[0].painted.size)
    throw Error("Paint an ROI before exporting it.");
  const manifest = {
    schema_version: 2,
    atlas: atlas.atlas,
    atlas_version: atlas.atlas_version,
    atlas_resolution_um: atlas.atlas_resolution_um,
    atlas_shape: atlas.atlas_shape,
    coordinate_units: "um",
    axis_order: ["AP", "DV", "ML"],
    coordinate_origin: "BrainGlobe atlas origin",
    paint_color: state.paintColor,
    mirror_color: state.mirrorColor,
    created_utc: new Date().toISOString(),
    regions: [],
    cells_file: null,
  };
  const files = {};
  const add = (name, data) =>
    (files[name] = strToU8(
      typeof data === "string" ? data : JSON.stringify(data, null, 2),
    ));
  for (const r of regions) {
    const safe = r.acronym.replace(/[^a-zA-Z0-9_-]/g, "_") + "_" + r.id,
      ids = [...r.painted].sort((a, b) => a - b),
      hash = await geometryHash(r.vertices, r.faces),
      item = {
        area: r.acronym,
        name: r.name,
        structure_id: r.id,
        color: r.color,
        visible: r.visible,
        n_painted_faces: ids.length,
        mesh_geometry_sha256: hash,
      };
    if (!activeOnly) {
      item.full_mesh_file = safe + "_full_mesh.ply";
      add(item.full_mesh_file, ply(r.vertices, r.faces));
    }
    if (ids.length) {
      const mesh = safe + "_painted_roi.ply",
        table = safe + "_painted_face_ids.csv",
        meta = safe + "_metadata.json";
      add(mesh, ply(r.vertices, r.faces, ids));
      add(
        table,
        csv([
          ["area", "face_id", "center_x_um", "center_y_um", "center_z_um"],
          ...ids.map((id) => [
            r.acronym,
            id,
            ...r.centroids.slice(id * 3, id * 3 + 3),
          ]),
        ]),
      );
      const metadata = { ...manifest };
      delete metadata.regions;
      delete metadata.cells_file;
      add(meta, {
        ...metadata,
        mesh_geometry_sha256: hash,
        area: r.acronym,
        region_name: r.name,
        structure_id: r.id,
        n_painted_faces: ids.length,
        ply_file: mesh,
        face_ids_file: table,
        region_color: r.color,
        mirrored_face_ids: [...r.mirrored].sort((a, b) => a - b),
      });
      Object.assign(item, {
        painted_roi_file: mesh,
        painted_face_ids_file: table,
        metadata_file: meta,
      });
    }
    manifest.regions.push(item);
  }
  if (state.cells && !activeOnly) {
    const imported = state.cells,
      columns = imported.headers.filter(
        (h) =>
          !["app_x_um", "app_y_um", "app_z_um", "app_selected"].includes(h),
      );
    manifest.cells_file = "imported_cells_atlas_coordinates.csv";
    manifest.cell_coordinate_mode = imported.units;
    manifest.cell_label_column = state.labelColumn;
    manifest.cell_color_column = state.colorColumn;
    manifest.selected_cell_count = imported.cells.filter(
      (c) => c.visible,
    ).length;
    add(
      manifest.cells_file,
      csv([
        [...columns, "app_x_um", "app_y_um", "app_z_um", "app_selected"],
        ...imported.cells.map((c) => [
          ...columns.map((h) => c.row[h]),
          ...c.xyz,
          c.visible,
        ]),
      ]),
    );
  }
  add("scene_manifest.json", manifest);
  download(
    zipSync(files, { level: 6 }),
    `allen_${activeOnly ? "roi" : "scene"}_${Date.now()}.zip`,
    "application/zip",
  );
}
export function projectData(state) {
  return {
    format: "allen-reference-painter-project",
    version: 1,
    atlas: state.manifest.atlas,
    atlas_version: state.manifest.atlas_version,
    active: state.active,
    paintColor: state.paintColor,
    mirrorColor: state.mirrorColor,
    labelColumn: state.labelColumn,
    colorColumn: state.colorColumn,
    cells: state.cells,
    regions: [...state.regions.values()].map((r) => ({
      id: r.id,
      mesh_geometry_sha256: r.mesh_geometry_sha256,
      painted: [...r.painted],
      mirrored: [...r.mirrored],
      visible: r.visible,
      opacity: r.opacity,
    })),
  };
}
export function validateProject(data, manifest) {
  if (
    data?.format !== "allen-reference-painter-project" ||
    data.version !== 1 ||
    data.atlas !== manifest.atlas ||
    data.atlas_version !== manifest.atlas_version ||
    !Array.isArray(data.regions)
  )
    throw Error("This is not a compatible BrainGlobe 3.1 painter project.");
  const seen = new Set();
  for (const r of data.regions) {
    const source = manifest.regions.find((x) => x.id === r.id);
    if (
      !source?.file ||
      seen.has(r.id) ||
      source.mesh_geometry_sha256 !== r.mesh_geometry_sha256
    )
      throw Error("Project mesh identity does not match this atlas.");
    seen.add(r.id);
    for (const key of ["painted", "mirrored"])
      if (
        !Array.isArray(r[key]) ||
        r[key].some(
          (x) => !Number.isInteger(x) || x < 0 || x >= source.triangles,
        )
      )
        throw Error("Project contains an invalid face ID.");
    const painted = new Set(r.painted);
    if (
      r.mirrored.some((i) => !painted.has(i)) ||
      typeof r.visible !== "boolean" ||
      !Number.isFinite(r.opacity) ||
      r.opacity < 0.1 ||
      r.opacity > 1
    )
      throw Error("Invalid region state in project.");
  }
  if (data.active !== null && !seen.has(data.active))
    throw Error("Invalid active region in project.");
  for (const key of ["paintColor", "mirrorColor"])
    if (!/^#[a-fA-F0-9]{6}$/.test(data[key]))
      throw Error("Invalid paint color in project.");
  if (data.cells !== null && data.cells !== undefined) {
    const c = data.cells;
    if (
      !Array.isArray(c.headers) ||
      !c.headers.every((h) => typeof h === "string") ||
      !Array.isArray(c.cells) ||
      !["um", "mm", "voxel"].includes(c.units)
    )
      throw Error("Invalid cell table in project.");
    for (const cell of c.cells)
      if (
        !cell.row ||
        typeof cell.row !== "object" ||
        !Array.isArray(cell.xyz) ||
        cell.xyz.length !== 3 ||
        !cell.xyz.every(Number.isFinite) ||
        typeof cell.visible !== "boolean"
      )
        throw Error("Invalid cell coordinates in project.");
  }
  return data;
}
