// Labeled surface masks retain exact original face IDs, including overlaps.
export function newLayer(name = 'Untitled ROI', color = '#ff795f', mirrorColor = '#55d9e7') {
  return { id: crypto.randomUUID(), name, tags: '', color, mirrorColor, visible: true, painted: [], mirrored: [] };
}
export function ensureLayers(r, color, mirrorColor) {
  if (!r.layers) {
    const layer = newLayer('ROI', color, mirrorColor);
    layer.painted = [...r.painted]; layer.mirrored = [...r.mirrored];
    r.layers = [layer]; r.activeLayer = layer.id;
  }
  return r.layers.find(l => l.id === r.activeLayer) || r.layers[0];
}
export function syncPaint(r) {
  r.painted = new Set(r.layers.flatMap(l => l.painted));
  r.mirrored = new Set(r.layers.flatMap(l => l.mirrored));
}
export function snapshot(r) { return JSON.parse(JSON.stringify({ layers: r.layers, activeLayer: r.activeLayer })); }
export function restore(r, data) { Object.assign(r, structuredClone(data)); syncPaint(r); }
export function adjacency(r) {
  if (r.adjacency) return r.adjacency;
  const edges = new Map(), neighbors = Array.from({ length: r.faces.length / 3 }, () => new Set());
  for (let f = 0; f < neighbors.length; f++) for (let k = 0; k < 3; k++) {
    const a = r.faces[f * 3 + k], b = r.faces[f * 3 + (k + 1) % 3];
    const key = a < b ? a + ':' + b : b + ':' + a;
    const others = edges.get(key) || [];
    for (const other of others) { neighbors[f].add(other); neighbors[other].add(f); }
    others.push(f); edges.set(key, others);
  }
  return r.adjacency = neighbors.map(n => [...n]);
}
export function surfaceBrush(r, face, point, radius) {
  const allowed = new Set(r.index.near(point, radius)); allowed.add(face);
  const neighbors = adjacency(r), visited = new Set([face]), queue = [face];
  for (let i = 0; i < queue.length; i++) for (const n of neighbors[queue[i]])
    if (allowed.has(n) && !visited.has(n)) { visited.add(n); queue.push(n); }
  return queue;
}
export function modifyMask(r, layer, operation) {
  const before = new Set(layer.painted), neighbors = adjacency(r), result = new Set(before);
  for (let f = 0; f < neighbors.length; f++) {
    const ns = neighbors[f], count = ns.filter(n => before.has(n)).length;
    if (operation === 'fill') result.add(f);
    if (operation === 'invert') before.has(f) ? result.delete(f) : result.add(f);
    if (operation === 'grow' && count) result.add(f);
    if (operation === 'shrink' && count < ns.length) result.delete(f);
    if (operation === 'smooth' && ns.length) count > ns.length / 2 ? result.add(f) : result.delete(f);
  }
  layer.painted = [...result];
  const mirrored = new Set(layer.mirrored);
  layer.mirrored = [...result].filter(f => mirrored.has(f) ||
    (operation === 'grow' && neighbors[f].some(n => mirrored.has(n))));
  syncPaint(r);
}
