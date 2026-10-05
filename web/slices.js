import { loadSlice } from "./atlas.js";
export class Slices {
  constructor(manifest, state, viewer, status) {
    this.manifest = manifest;
    this.state = state;
    this.viewer = viewer;
    this.status = status;
    this.ids = new Map(manifest.regions.map((r) => [r.id, r]));
    this.entries = [
      { name: "coronal", axis: 0, h: 2, index: 300 },
      { name: "sagittal", axis: 2, h: 0, index: 170 },
    ];
    this.marker = null;
    for (const e of this.entries) {
      e.canvas = document.getElementById(e.name);
      e.slider = document.getElementById(e.name + "-depth");
      e.input = document.getElementById(e.name + "-index");
      e.width = manifest.atlas_shape[e.h];
      e.height = manifest.atlas_shape[1];
      e.generation = 0;
      const change = (v) => {
        e.index = Math.max(
          0,
          Math.min(
            manifest.atlas_shape[e.axis] - 1,
            Math.round(Number(v)) || 0,
          ),
        );
        this.load(e);
      };
      e.slider.oninput = () => change(e.slider.value);
      e.input.onchange = () => change(e.input.value);
      document.getElementById("find-" + e.name).onclick = () => this.focus(e);
      e.canvas.onpointermove = (event) => {
        const p = this.point(e, event);
        if (!p || !e.labels) return;
        const sid = e.labels[p[1] * e.width + p[0]],
          r = this.ids.get(sid);
        const xyz = [0, p[1] * 25, 0]; xyz[e.h] = p[0] * 25; xyz[e.axis] = e.index * 25;
        document.getElementById("slice-hover").textContent =
          `AP ${xyz[0]} · DV ${xyz[1]} · ML ${xyz[2]} µm · ${r ? r.acronym + ' · ' + r.name : 'Outside atlas'}`;
      };
      e.canvas.onpointerleave = () => { document.getElementById("slice-hover").textContent = "Hover a slice for AP · DV · ML coordinates (µm)."; };
      e.canvas.onclick = (event) => {
        const p = this.point(e, event);
        if (!p) return;
        const xyz = [0, p[1] * 25, 0];
        xyz[e.h] = p[0] * 25;
        xyz[e.axis] = e.index * 25;
        this.marker = xyz;
        viewer.setMarker(xyz);
        const other = this.entries.find((x) => x !== e);
        other.index = Math.round(xyz[other.axis] / 25);
        this.load(other);
        this.draw(e);
      };
      new ResizeObserver(() => this.draw(e)).observe(e.canvas);
    }
    document.getElementById("planes").onchange = () => this.planes();
    this.entries.forEach((e) => this.load(e));
  }
  point(e, event) {
    if (!e.projection) return null;
    const rect = e.canvas.getBoundingClientRect(),
      { scale, x, y } = e.projection,
      px = Math.floor(
        (((event.clientX - rect.left) * e.canvas.width) / rect.width - x) /
          scale,
      ),
      py = Math.floor(
        (((event.clientY - rect.top) * e.canvas.height) / rect.height - y) /
          scale,
      );
    return px >= 0 && px < e.width && py >= 0 && py < e.height
      ? [px, py]
      : null;
  }
  async load(e) {
    const generation = ++e.generation;
    e.slider.value = e.index;
    e.input.value = e.index;
    document.getElementById(e.name + "-position").textContent =
      `${(e.index * 25).toLocaleString()} µm · slice ${e.index}`;
    e.labels = null;
    this.draw(e);
    this.planes();
    try {
      const labels = await loadSlice(e.axis, e.index, e.width, e.height);
      if (generation !== e.generation) return;
      e.labels = labels;
      this.draw(e);
    } catch (err) {
      if (generation === e.generation) {
        e.error = err.message;
        this.draw(e);
        this.status(err.message, true);
      }
    }
  }
  focus(e) {
    const r = this.state.regions.get(this.state.active);
    if (!r) return;
    let lo = Infinity,
      hi = -Infinity;
    for (let i = e.axis; i < r.vertices.length; i += 3) {
      lo = Math.min(lo, r.vertices[i]);
      hi = Math.max(hi, r.vertices[i]);
    }
    e.index = Math.max(
      0,
      Math.min(
        this.manifest.atlas_shape[e.axis] - 1,
        Math.round((lo + hi) / 50),
      ),
    );
    this.load(e);
  }
  planes() {
    this.viewer.setPlanes(
      this.entries[0].index * 25,
      this.entries[1].index * 25,
      document.getElementById("planes").checked,
    );
  }
  refresh() {
    this.entries.forEach((e) => this.draw(e));
  }
  draw(e) {
    if (!e.canvas.clientWidth) return;
    const dpr = Math.min(devicePixelRatio, 2),
      w = Math.round(e.canvas.clientWidth * dpr),
      h = Math.round(e.canvas.clientHeight * dpr);
    e.canvas.width = w;
    e.canvas.height = h;
    const ctx = e.canvas.getContext("2d");
    ctx.fillStyle = "#f5f8fb";
    ctx.fillRect(0, 0, w, h);
    const scale = Math.min((w - 18 * dpr) / e.width, (h - 16 * dpr) / e.height),
      x = (w - e.width * scale) / 2,
      y = (h - e.height * scale) / 2;
    e.projection = { scale, x, y };
    if (!e.labels) {
      ctx.fillStyle = "#748c9e";
      ctx.font = `${12 * dpr}px system-ui`;
      ctx.textAlign = "center";
      ctx.fillText(
        e.error ? "Slice unavailable — move slider to retry" : "Loading slice…",
        w / 2,
        h / 2,
      );
      return;
    }
    const off = document.createElement("canvas");
    off.width = e.width;
    off.height = e.height;
    const octx = off.getContext("2d"),
      im = octx.createImageData(e.width, e.height),
      active = this.state.regions.get(this.state.active),
      highlight = new Set(
        this.manifest.regions
          .filter((r) => active && r.path.includes(active.id))
          .map((r) => r.id),
      );
    for (let i = 0; i < e.labels.length; i++) {
      const id = e.labels[i];
      if (!id) continue;
      const info = this.ids.get(id),
        c = info?.color || "#95a8b5",
        rgb = [1, 3, 5].map((j) => parseInt(c.slice(j, j + 2), 16));
      let alpha = highlight.has(id) ? 0.7 : 0.14;
      const row = Math.floor(i / e.width),
        col = i % e.width;
      if (
        (col < e.width - 1 && e.labels[i + 1] !== id) ||
        (row < e.height - 1 && e.labels[i + e.width] !== id)
      )
        alpha = Math.max(alpha, 0.45);
      im.data.set([...rgb, Math.round(alpha * 255)], i * 4);
    }
    octx.putImageData(im, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(off, x, y, e.width * scale, e.height * scale);
    const dot = (xyz, color, r) => {
      if (Math.abs(xyz[e.axis] - e.index * 25) > 50) return;
      ctx.beginPath();
      ctx.fillStyle = color;
      ctx.arc(
        x + (xyz[e.h] / 25) * scale,
        y + (xyz[1] / 25) * scale,
        r * dpr,
        0,
        Math.PI * 2,
      );
      ctx.fill();
    };
    for (const r of this.state.regions.values()) if (r.visible)
      for (const layer of r.layers || []) if (layer.visible) {
        const mirrored = new Set(layer.mirrored);
        for (const id of layer.painted) dot(r.centroids.slice(id * 3, id * 3 + 3), mirrored.has(id) ? layer.mirrorColor : layer.color, 1.3);
      }
    for (const c of this.state.cells?.cells || [])
      if (c.visible) dot(c.xyz, this.state.cellColor(c), 2.3);
    const other = this.entries.find((a) => a !== e);
    ctx.setLineDash([3 * dpr, 3 * dpr]);
    ctx.lineWidth = dpr;
    ctx.strokeStyle = e.axis === 0 ? "#36b3c7" : "#b79337";
    ctx.beginPath();
    const px = x + other.index * scale;
    ctx.moveTo(px, y);
    ctx.lineTo(px, y + e.height * scale);
    ctx.stroke();
    ctx.setLineDash([]);
    if (this.marker) {
      const px = x + (this.marker[e.h] / 25) * scale,
        py = y + (this.marker[1] / 25) * scale;
      ctx.strokeStyle = "#193d56";
      ctx.beginPath();
      ctx.moveTo(px - 5 * dpr, py);
      ctx.lineTo(px + 5 * dpr, py);
      ctx.moveTo(px, py - 5 * dpr);
      ctx.lineTo(px, py + 5 * dpr);
      ctx.stroke();
    }
  }
  screenshot() {
    const c = document.createElement("canvas");
    c.width = Math.max(...this.entries.map((e) => e.canvas.width));
    c.height = this.entries.reduce((s, e) => s + e.canvas.height + 32, 0);
    const ctx = c.getContext("2d");
    ctx.fillStyle = "white";
    ctx.fillRect(0, 0, c.width, c.height);
    let y = 0;
    for (const e of this.entries) {
      ctx.fillStyle = "#183349";
      ctx.font = "14px system-ui";
      ctx.fillText(
        `${e.name} · ${e.index * 25} µm · BrainGlobe atlas origin`,
        10,
        y + 21,
      );
      ctx.drawImage(e.canvas, 0, y + 32);
      y += e.canvas.height + 32;
    }
    return c.toDataURL("image/png");
  }
}
