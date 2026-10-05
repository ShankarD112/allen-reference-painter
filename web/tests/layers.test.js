import test from 'node:test';
import assert from 'node:assert/strict';
import { zipSync, strToU8 } from 'fflate';
import { ensureLayers, syncPaint, modifyMask, surfaceBrush, snapshot, restore } from '../paint.js';
import { readProject, mergeProjects } from '../session.js';
import { projectData, validateProject } from '../export.js';
const source = { id: 1, file: 'mesh', triangles: 3, mesh_geometry_sha256: 'verified' };
const manifest = { atlas: 'test', atlas_version: '3.1', atlas_shape: [528,320,456], regions: [source] };
function region() {
  const r = { ...source, faces: new Uint32Array([0,1,2, 2,1,3, 4,5,6]), painted: new Set([0]), mirrored: new Set(), visible: true, opacity: 0.8,
    index: { near: () => [0,1,2] } };
  ensureLayers(r); return r;
}
function project() {
  const r = region();
  return projectData({ manifest, active: 1, paintColor: '#ff795f', mirrorColor: '#55d9e7', cells: null, regions: new Map([[1,r]]) });
}
test('surface brush does not cross disconnected nearby surfaces; grow/shrink and undo preserve face IDs', () => {
  const r = region(), l = r.layers[0], saved = snapshot(r);
  assert.deepEqual(surfaceBrush(r, 0, [0,0,0], 250), [0,1]);
  modifyMask(r,l,'grow'); assert.deepEqual(l.painted,[0,1]);
  modifyMask(r,l,'invert'); assert.deepEqual(l.painted,[2]);
  restore(r,saved); assert.deepEqual([...r.painted],[0]);
});
test('multiple imported masks on same mesh remain separate, with overlapping faces and labels retained', () => {
  const a = project(), b = project(); b.regions[0].layers[0].name = 'Treatment'; b.regions[0].layers[0].tags = 'animal-2';
  const combined = mergeProjects(a,b,'experiment.zip');
  assert.equal(combined.regions.length,1); assert.equal(combined.regions[0].layers.length,2);
  assert.equal(new Set(combined.regions[0].layers.map(l => l.id)).size,2);
  assert.equal(combined.regions[0].layers[1].source,'experiment.zip');
  assert.equal(combined.regions[0].layers[1].tags,'animal-2');
  assert.deepEqual(combined.regions[0].painted,[0]); validateProject(combined,manifest);
});
test('ZIP project roundtrip retains labels and rejects invalid layer face IDs before mutation', async () => {
  const p = project(); p.regions[0].layers[0].name = '<script>literal label</script>';
  const bytes = zipSync({'project.json':strToU8(JSON.stringify(p))});
  const file = new File([bytes],'scene.zip');
  assert.deepEqual(await readProject(file,manifest),JSON.parse(JSON.stringify(p)));
  p.regions[0].layers[0].painted = [99]; assert.throws(() => validateProject(p,manifest),/face ID/);
});
test('legacy analysis ZIP restores exact face IDs and mirror state', async () => {
  const scene = { schema_version:2, atlas:'test', atlas_version:'3.1',paint_color:'#ff795f',mirror_color:'#55d9e7',regions:[{
    structure_id:1,mesh_geometry_sha256:'verified',visible:true,painted_face_ids_file:'faces.csv',metadata_file:'meta.json'
  }] };
  const zip = zipSync({'scene_manifest.json':strToU8(JSON.stringify(scene)), 'faces.csv':strToU8('area,face_id\nROI,0\nROI,1\n'), 'meta.json':strToU8('{"mirrored_face_ids":[1]}')});
  const p = await readProject(new File([zip],'old.zip'),manifest);
  assert.deepEqual(p.regions[0].painted,[0,1]); assert.deepEqual(p.regions[0].mirrored,[1]);
});
test('hidden masks stay saved and overlapping masks survive clearing another layer', () => {
  const r=region(); r.layers.push({...structuredClone(r.layers[0]),id:'second', visible:false});
  r.layers[0].painted=[]; syncPaint(r); assert.deepEqual([...r.painted],[0]);
});

test('3D paint uses opaque unlit overlays independent of translucent base and follows layer visibility', async () => {
  const T = await import('three');
  const { Viewer } = await import('../viewer.js');
  const viewer = Object.create(Viewer.prototype);
  viewer.scene = new T.Scene(); viewer.regions = new Map(); viewer.render = () => {};
  const r = region(); r.color = '#0088ff'; r.acronym = 'ROI'; r.name = 'Test region';
  r.vertices = new Float64Array([0,0,0, 100,0,0, 0,100,0, 100,100,0, 0,0,25, 100,0,25, 0,100,25]);
  viewer.add(r);
  assert.equal(r.mesh.material.opacity,0.8);
  assert.equal(r.overlays.length,1);
  assert.equal(r.overlays[0].material.type,'MeshBasicMaterial');
  assert.equal(r.overlays[0].material.opacity,1);
  assert.equal(r.overlays[0].geometry.attributes.position.count,3);
  r.opacity=0.1; r.layers[0].visible=false; viewer.update(r);
  assert.equal(r.overlays[0].visible,false);
  r.layers[0].visible=true; viewer.update(r);
  assert.equal(r.overlays[0].visible,true);
  assert.equal(r.overlays[0].material.opacity,1);
  viewer.remove(r.id); assert.equal(viewer.scene.children.length,0);
});

test('layer-number searches do not accidentally match digits in structure IDs', async () => {
  const { findRegions } = await import('../regions.js');
  const one = {id:97,acronym:'ENTl1',name:'Entorhinal area, lateral part, layer 1',path:[1,2]};
  const five = {id:115,acronym:'ENTl5',name:'Entorhinal area, lateral part, layer 5',path:[1,2]};
  assert.deepEqual(findRegions([five,one],'Entorhinal area, lateral part, layer 1'),[one]);
  assert.deepEqual(findRegions([five,one],'115'),[five]);
  assert.deepEqual(findRegions([five,one],'ENT'),[one,five]);
  assert.deepEqual(findRegions([five,one],'ENT','3'),[]);
});
