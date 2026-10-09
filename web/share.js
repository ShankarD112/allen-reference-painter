import { download } from './export.js';
export async function exportHTML(viewer, colorInfo) {
  const response = await fetch(new URL('share/viewer.js', document.baseURI));
  if (!response.ok) throw Error('Standalone viewer runtime unavailable. Retry after the app has finished deploying.');
  const runtime = await response.text();
  if (!runtime.includes('scene-data')) throw Error('Invalid standalone viewer runtime.');
  const scene = viewer.scene.clone(true);
  // Do not serialize temporary cursor, crosshair or reference planes.
  const transient = new Set([viewer.brush?.uuid, viewer.marker.uuid, ...viewer.planes.map(p => p.uuid)]);
  for (let i = viewer.scene.children.length - 1; i >= 0; i--) if (transient.has(viewer.scene.children[i].uuid)) scene.remove(scene.children[i]);
  const cellColoring = colorInfo ? {label:colorInfo.label,source:colorInfo.source,key:colorInfo.key,range:colorInfo.range,categories:colorInfo.categories,missing:colorInfo.missing} : null;
  const data = JSON.stringify({ cellColoring, scene: scene.toJSON(), position: viewer.camera.position.toArray(), target: viewer.controls.target.toArray() }).replaceAll('<', '\\u003c');
  const html = `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Reference Painter — shared scene</title><style>
  *{box-sizing:border-box}body{margin:0;background:#0c1b2b;color:#183349;font:14px system-ui}#viewer{position:fixed;inset:0}aside{position:relative;z-index:2;background:#ffffffed;padding:18px;margin:16px;border-radius:12px;width:290px;max-height:85vh;overflow:auto}h1{font-size:20px}label{display:flex;gap:8px;padding:8px 0}span{padding-left:6px;overflow-wrap:anywhere}input[type=search]{width:100%;padding:8px}button{padding:8px;margin-top:12px}[hidden]{display:none!important}@media(max-width:600px){aside{max-height:30vh;width:calc(100% - 32px)}}
  </style><div id="viewer"></div><aside><h1>Reference Painter</h1><p>Drag to orbit · scroll to zoom · right drag to pan</p><p>Atlas surface masks · BrainGlobe 3.1 · AP / DV / ML</p><input id="filter" type="search" aria-label="Filter regions and labels" placeholder="Find labels or tags"><div id="cell-color-legend"></div><div id="legend"></div><button id="reset">Reset view</button></aside><script id="scene-data" type="application/json">${data}</script><script>${runtime.replace(/<\/script/gi, '<\\/script')}</script></html>`;
  download(html, `allen_painter_interactive_${Date.now()}.html`, 'text/html');
}
