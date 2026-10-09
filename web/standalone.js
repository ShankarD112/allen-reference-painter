import * as T from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
const data = JSON.parse(document.getElementById('scene-data').textContent);
const scene = new T.ObjectLoader().parse(data.scene);
const camera = new T.PerspectiveCamera(36, innerWidth / innerHeight, 0.01, 150);
camera.position.fromArray(data.position);
const renderer = new T.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = T.SRGBColorSpace;
document.getElementById('viewer').append(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.fromArray(data.target); controls.update();
const render = () => renderer.render(scene, camera);
controls.addEventListener('change', render);
const resize = () => { const host = document.getElementById('viewer'); camera.aspect = host.clientWidth / host.clientHeight; camera.updateProjectionMatrix(); renderer.setSize(host.clientWidth, host.clientHeight); render(); };
window.addEventListener('resize', resize);
const items = [], regionVisible = new Map();
scene.traverse(object => { if (object.userData.kind === 'region') regionVisible.set(object.userData.regionId, object.visible); });
scene.traverse(object => {
  if (!['region', 'layer'].includes(object.userData.kind)) return;
  const row = document.createElement('label'), check = document.createElement('input'), text = document.createElement('span');
  check.type = 'checkbox'; check.checked = object.userData.kind === 'layer' ? object.userData.layerVisible : object.visible;
  text.textContent = object.userData.kind === 'layer' ? `${object.userData.region} / ${object.name}${object.userData.tags ? ' · ' + object.userData.tags : ''}${object.userData.source ? ' — ' + object.userData.source : ''}` : object.name;
  if (object.userData.color) text.style.borderLeft = '5px solid ' + object.userData.color;
  row.append(check, text); document.getElementById('legend').append(row); items.push({ row, check, object });
  check.onchange = () => {
    if (object.userData.kind === 'region') regionVisible.set(object.userData.regionId, check.checked);
    for (const item of items) item.object.visible = item.check.checked && (item.object.userData.kind !== 'layer' || regionVisible.get(item.object.userData.regionId));
    render();
  };
});
document.getElementById('filter').oninput = event => items.forEach(item => item.row.hidden = !item.row.textContent.toLowerCase().includes(event.target.value.toLowerCase()));
document.getElementById('reset').onclick = () => { camera.position.fromArray(data.position); controls.target.fromArray(data.target); controls.update(); render(); };
resize();

if(data.cellColoring){
 const info=data.cellColoring,host=document.getElementById('cell-color-legend');
 const title=document.createElement('h2');title.style.fontSize='14px';title.textContent=info.label;host.append(title);
 if(info.range){const bar=document.createElement('div');bar.style.cssText='height:8px;background:linear-gradient(90deg,#2c70b4,#3dd1be,#ffd966);border-radius:4px';const range=document.createElement('p');range.textContent=info.range.join(' – ');host.append(bar,range);}
 for(const category of info.categories){const row=document.createElement('p');row.textContent=category.label;row.style.borderLeft='6px solid '+category.color;row.style.paddingLeft='8px';host.append(row);}
 if(info.source!=='single'){const missing=document.createElement('p');missing.textContent=info.missing+' cells with missing values (gray).';host.append(missing);}
}
