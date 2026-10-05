import { unzipSync, strFromU8 } from 'fflate';
import Papa from 'papaparse';
import { validateProject } from './export.js';
import { newLayer } from './paint.js';
export async function readProject(file, manifest) {
  if (file.size > 150 * 1024 * 1024) throw Error('Import files must be smaller than 150 MB.');
  if (!/\.zip$/i.test(file.name)) return validateProject(JSON.parse(await file.text()), manifest);
  let total = 0;
  const files = unzipSync(new Uint8Array(await file.arrayBuffer()), { filter(entry) {
    if (!/\.(json|csv)$/.test(entry.name)) return false;
    total += entry.originalSize;
    if (total > 150 * 1024 * 1024) throw Error('Expanded project data exceeds 150 MB.');
    return true;
  }});
  const json = name => {
    if (!files[name]) throw Error(`ZIP is missing ${name}.`);
    return JSON.parse(strFromU8(files[name]));
  };
  if (files['project.json']) return validateProject(json('project.json'), manifest);
  // Legacy web analysis exports (schema 2) can also be resumed.
  const scene = json('scene_manifest.json');
  if (scene.schema_version !== 2 || scene.atlas !== manifest.atlas || scene.atlas_version !== manifest.atlas_version || !Array.isArray(scene.regions))
    throw Error('This ZIP is not a compatible painter export.');
  const data = { format: 'allen-reference-painter-project', version: 1,
    atlas: scene.atlas, atlas_version: scene.atlas_version, active: scene.regions[0]?.structure_id ?? null,
    paintColor: scene.paint_color, mirrorColor: scene.mirror_color, cells: null, regions: [] };
  for (const item of scene.regions) {
    let painted = [], mirrored = [];
    if (item.painted_face_ids_file) {
      if (!files[item.painted_face_ids_file]) throw Error('Missing ROI face table.');
      const table = Papa.parse(strFromU8(files[item.painted_face_ids_file]), { header: true, skipEmptyLines: true });
      if (table.errors.length) throw Error('Invalid ROI face table.');
      painted = table.data.map(row => Number(row.face_id));
      mirrored = json(item.metadata_file).mirrored_face_ids || [];
    }
    data.regions.push({ id: item.structure_id, mesh_geometry_sha256: item.mesh_geometry_sha256,
      painted, mirrored, visible: item.visible ?? true, opacity: item.opacity ?? 0.8 });
  }
  if (scene.cells_file) {
    if (!files[scene.cells_file]) throw Error('Missing exported cell table.');
    const table = Papa.parse(strFromU8(files[scene.cells_file]), { header: true, skipEmptyLines: true });
    if (table.errors.length) throw Error('Invalid cell table.');
    const headers = table.meta.fields.filter(h => !['app_x_um','app_y_um','app_z_um','app_selected'].includes(h));
    data.cells = { units: scene.cell_coordinate_mode || 'um', headers, cells: table.data.map(row => ({
      row: Object.fromEntries(headers.map(h => [h, row[h]])), xyz: ['app_x_um','app_y_um','app_z_um'].map(k => Number(row[k])), visible: row.app_selected === 'true'
    })) };
    data.labelColumn = scene.cell_label_column; data.colorColumn = scene.cell_color_column;
  }
  return validateProject(data, manifest);
}
export function mergeProjects(base, incoming, sourceName) {
  const output = structuredClone(base);
  for (const saved of incoming.regions) {
    const copy = structuredClone(saved);
    if (!copy.layers) {
      const layer = newLayer('ROI', incoming.paintColor, incoming.mirrorColor);
      Object.assign(layer, { painted: copy.painted, mirrored: copy.mirrored }); copy.layers = [layer];
    }
    copy.layers = copy.layers.map(layer => ({ ...layer, id: crypto.randomUUID(), source: sourceName }));
    copy.activeLayer = copy.layers[0]?.id;
    const existing = output.regions.find(r => r.id === copy.id);
    if (existing) {
      if (!existing.layers) {
        const layer = newLayer('ROI', base.paintColor, base.mirrorColor);
        Object.assign(layer, { painted: existing.painted, mirrored: existing.mirrored }); existing.layers = [layer]; existing.activeLayer = layer.id;
      }
      existing.layers.push(...copy.layers);
      existing.painted = [...new Set(existing.layers.flatMap(l => l.painted))];
      existing.mirrored = [...new Set(existing.layers.flatMap(l => l.mirrored))];
    } else output.regions.push(copy);
  }
  if (incoming.cells) {
    if (!output.cells) output.cells = structuredClone(incoming.cells);
    else {
      output.cells.headers = [...new Set([...output.cells.headers, ...incoming.cells.headers])];
      output.cells.cells.push(...structuredClone(incoming.cells.cells));
    }
  }
  output.active ??= incoming.active;
  return output;
}
