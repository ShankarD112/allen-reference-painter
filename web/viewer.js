import * as T from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { ensureLayers } from "./paint.js";
import { toDisplay, fromDisplay } from "./core.js";

export class Viewer {
  constructor(host, callbacks) {
    this.host = host;
    this.callbacks = callbacks;
    this.mode = "navigate";
    this.regions = new Map();
    this.scene = new T.Scene();
    this.camera = new T.PerspectiveCamera(36, 1, 0.01, 150);
    this.camera.position.set(18, 12, 17);
    this.renderer = new T.WebGLRenderer({
      antialias: true,
      alpha: true,
      preserveDrawingBuffer: true,
    });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.outputColorSpace = T.SRGBColorSpace;
    host.append(this.renderer.domElement);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.target.set(0, 0, 0);
    this.controls.enableDamping = false;
    this.controls.minDistance = 0.5;
    this.controls.maxDistance = 60;
    this.controls.addEventListener("change", () => this.render());
    this.scene.add(new T.HemisphereLight(0xcfefff, 0x52687d, 2.2));
    const key = new T.DirectionalLight(0xfff4dd, 2.7);
    key.position.set(5, 12, 8);
    this.scene.add(key);
    const fill = new T.DirectionalLight(0x73bacb, 1.2);
    fill.position.set(-10, -3, -6);
    this.scene.add(fill);
    this.raycaster = new T.Raycaster();
    this.pointer = new T.Vector2();
    this.marker = new T.Mesh(
      new T.SphereGeometry(0.075, 12, 8),
      new T.MeshBasicMaterial({ color: 0xffdd77, depthTest: false }),
    );
    this.marker.visible = false;
    this.marker.renderOrder = 8;
    this.scene.add(this.marker);
    this.planes = [0, 2].map((axis) => {
      const mesh = new T.Mesh(
        new T.PlaneGeometry(axis === 0 ? 11.4 : 13.2, 8),
        new T.MeshBasicMaterial({
          color: axis === 0 ? 0xf0d37b : 0x52c7de,
          side: T.DoubleSide,
          transparent: true,
          opacity: 0.075,
          depthWrite: false,
        }),
      );
      if (axis === 2) mesh.rotation.y = Math.PI / 2;
      this.scene.add(mesh);
      return mesh;
    });
    this.brush = new T.Mesh(new T.SphereGeometry(1, 20, 12), new T.MeshBasicMaterial({ color: 0xffffff, wireframe: true, transparent: true, opacity: 0.3, depthWrite: false }));
    this.brush.visible = false; this.scene.add(this.brush);
    const el = this.renderer.domElement;
    el.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 || this.mode === "navigate") return;
      const hit = this.hit(e);
      if (!hit) return;
      e.preventDefault();
      el.setPointerCapture(e.pointerId);
      this.drawing = true;
      callbacks.begin();
      callbacks.paint(hit);
    });
    el.addEventListener("pointermove", (e) => {
      const hit = this.hit(e);
      this.brush.visible = !!hit && this.mode !== 'navigate';
      if (hit) {
        callbacks.hover(hit);
        this.brush.position.set(...toDisplay(hit.point));
        this.brush.scale.setScalar(Number(document.getElementById('radius').value) / 1000);
      }
      this.render();
      if (this.drawing && hit) callbacks.paint(hit);
    });
    el.addEventListener("pointerleave", () => { this.brush.visible = false; this.render(); });
    const end = () => {
      if (this.drawing) {
        this.drawing = false;
        callbacks.end();
      }
    };
    el.addEventListener("pointerup", end);
    el.addEventListener("pointercancel", end);
    el.addEventListener("lostpointercapture", end);
    this.resize = new ResizeObserver(() => {
      const w = host.clientWidth,
        h = host.clientHeight;
      if (!w || !h) return;
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(w, h);
      this.render();
    });
    this.resize.observe(host);
  }
  render() {
    this.renderer.render(this.scene, this.camera);
  }
  setMode(mode) {
    this.mode = mode;
    if (this.brush) this.brush.visible = false;
    this.controls.enabled = mode === "navigate";
    this.renderer.domElement.style.cursor =
      mode === "navigate" ? "grab" : "crosshair";
  }
  hit(event) {
    const region = this.regions.get(this.active);
    if (!region?.visible) return null;
    const r = this.renderer.domElement.getBoundingClientRect();
    this.pointer.set(
      ((event.clientX - r.left) / r.width) * 2 - 1,
      (-(event.clientY - r.top) / r.height) * 2 + 1,
    );
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const h = this.raycaster.intersectObject(region.mesh, false)[0];
    return h
      ? { point: fromDisplay(h.point.toArray()), face: h.faceIndex }
      : null;
  }
  geometry(region) {
    const positions = new Float32Array(region.faces.length * 3);
    for (let i = 0; i < region.faces.length; i++)
      positions.set(
        toDisplay(
          Array.from(
            region.vertices.slice(region.faces[i] * 3, region.faces[i] * 3 + 3),
          ),
        ),
        i * 3,
      );
    const g = new T.BufferGeometry();
    g.setAttribute("position", new T.BufferAttribute(positions, 3));
    g.computeVertexNormals();
    return g;
  }
  add(region, shell = false) {
    const g = this.geometry(region);
    const material = new T.MeshStandardMaterial({
      color: shell ? "#81a3b8" : "#ffffff",
      side: T.DoubleSide,
      transparent: true,
      opacity: shell ? 0.065 : region.opacity,
      roughness: 0.68,
      metalness: 0.05,
      depthWrite: !shell,
      vertexColors: false,
    });
    const mesh = new T.Mesh(g, material);
    if (shell) {
      this.shell = mesh;
      this.scene.add(mesh);
      return;
    }
    region.mesh = mesh;
    g.setAttribute(
      "color",
      new T.BufferAttribute(new Float32Array(region.faces.length * 3), 3),
    );
    this.regions.set(region.id, region);
    this.scene.add(mesh);
    mesh.name = region.acronym + " — " + region.name;
    mesh.userData = { kind: "region", regionId: region.id };
    this.update(region);
  }
  update(region) {
    region.mesh.material.color.set(region.color);
    region.mesh.material.opacity = region.opacity;
    region.mesh.material.depthWrite = region.opacity >= 0.95;
    region.mesh.visible = region.visible;
    for (const overlay of region.overlays || []) {
      this.scene.remove(overlay); overlay.geometry.dispose(); overlay.material.dispose();
    }
    region.overlays = [];
    ensureLayers(region, this.paintColor, this.mirrorColor);
    const source = region.mesh.geometry.attributes.position;
    for (const [index, layer] of region.layers.entries()) {
      if (!layer.painted.length) continue;
      const positions = new Float32Array(layer.painted.length * 9), colors = new Float32Array(positions.length);
      const painted = new T.Color(layer.color), mirror = new T.Color(layer.mirrorColor), mirrored = new Set(layer.mirrored);
      layer.painted.forEach((face, i) => {
        const color = mirrored.has(face) ? mirror : painted;
        for (let k = 0; k < 3; k++) {
          positions.set([source.getX(face * 3 + k), source.getY(face * 3 + k), source.getZ(face * 3 + k)], i * 9 + k * 3);
          colors.set([color.r, color.g, color.b], i * 9 + k * 3);
        }
      });
      const geometry = new T.BufferGeometry();
      geometry.setAttribute('position', new T.BufferAttribute(positions, 3));
      geometry.setAttribute('color', new T.BufferAttribute(colors, 3));
      // Unlit, opaque masks stay saturated while the anatomical mesh remains translucent.
      const overlay = new T.Mesh(geometry, new T.MeshBasicMaterial({ vertexColors: true, side: T.DoubleSide,
        polygonOffset: true, polygonOffsetFactor: -1 - index * 0.01, polygonOffsetUnits: -1 - index * 0.01 }));
      overlay.visible = region.visible && layer.visible; overlay.renderOrder = 2 + index;
      overlay.name = layer.name;
      overlay.userData = { kind: 'layer', regionId: region.id, layerId: layer.id, color: layer.color, tags: layer.tags, source: layer.source || '', region: region.acronym, layerVisible: layer.visible };
      this.scene.add(overlay); region.overlays.push(overlay);
    }
    this.render();
  }
  remove(id) {
    const r = this.regions.get(id);
    if (!r) return;
    for (const overlay of r.overlays || []) { this.scene.remove(overlay); overlay.geometry.dispose(); overlay.material.dispose(); }
    this.scene.remove(r.mesh);
    r.mesh.geometry.dispose();
    r.mesh.material.dispose();
    this.regions.delete(id);
    this.render();
  }
  focus(id) {
    const r = this.regions.get(id);
    if (!r) return;
    const box = new T.Box3().setFromObject(r.mesh),
      center = box.getCenter(new T.Vector3()),
      size = box.getSize(new T.Vector3()).length();
    const dir = this.camera.position
      .clone()
      .sub(this.controls.target)
      .normalize();
    this.controls.target.copy(center);
    this.camera.position
      .copy(center)
      .addScaledVector(dir, Math.max(size * 1.5, 3));
    this.controls.update();
    this.render();
  }
  view(name) {
    const offsets = {
      "3d": [18, 12, 17],
      coronal: [0, 0, 26],
      sagittal: [26, 0, 0],
      dorsal: [0, 26, 0.001],
    };
    this.camera.up.set(0, 1, 0);
    this.controls.target.set(0, 0, 0);
    this.camera.position.set(...offsets[name]);
    this.controls.update();
    this.render();
  }
  setPlanes(ap, ml, visible) {
    this.planes[0].position.set(0, 0, (6600 - ap) / 1000);
    this.planes[1].position.set((ml - 5700) / 1000, 0, 0);
    this.planes.forEach((p) => (p.visible = visible));
    this.render();
  }
  setMarker(xyz) {
    this.marker.position.set(...toDisplay(xyz));
    this.marker.visible = true;
    this.render();
  }
  setCells(cells, color) {
    if (this.cells) {
      this.scene.remove(this.cells);
      this.cells.geometry.dispose();
      this.cells.material.dispose();
    }
    const positions = [],
      colors = [];
    for (const cell of cells || [])
      if (cell.visible) {
        positions.push(...toDisplay(cell.xyz));
        const c = new T.Color(color(cell));
        colors.push(c.r, c.g, c.b);
      }
    const g = new T.BufferGeometry();
    g.setAttribute("position", new T.Float32BufferAttribute(positions, 3));
    g.setAttribute("color", new T.Float32BufferAttribute(colors, 3));
    this.cells = new T.Points(
      g,
      new T.PointsMaterial({
        size: 0.085,
        vertexColors: true,
        sizeAttenuation: true,
        depthTest: false,
        transparent: true,
        opacity: 0.95,
      }),
    );
    this.cells.renderOrder = 9;
    this.scene.add(this.cells);
    this.render();
  }
  screenshot() {
    this.render();
    return this.renderer.domElement.toDataURL("image/png");
  }
}
