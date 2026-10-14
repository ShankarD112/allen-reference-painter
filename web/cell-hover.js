// One non-interactive tooltip shared by the live workspace's cell views.
let provider = () => null;
let tooltip;
export function cellLabel(cell, state) {
  const column = state?.cells?.headers.find(
    (h) => h.trim().toLowerCase() === "cell_id",
  );
  const id = column && cell.row[column];
  if (id != null && String(id).trim()) return `cell_id: ${id}`;
  const label = state?.labelColumn && cell.row[state.labelColumn];
  return label != null && String(label).trim()
    ? String(label)
    : `Cell ${(state?.cells?.cells.indexOf(cell) ?? -1) + 1}`;
}
export function nearestCell(points, x, y, tolerance = 7) {
  let best = null,
    distance = Infinity;
  for (const point of points) {
    if (point.cell.visible === false) continue;
    const d = (point.x - x) ** 2 + (point.y - y) ** 2;
    const radius = Math.max(tolerance, point.radius || 0);
    if (d <= radius * radius && d < distance) {
      best = point.cell;
      distance = d;
    }
  }
  return best;
}
export function setupCellHover(getState) {
  provider = getState;
  window.addEventListener("scroll", hideCellHover, true);
  window.addEventListener("blur", hideCellHover);
  window.addEventListener("resize", hideCellHover);
  document.addEventListener("pointerdown", hideCellHover, true);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") hideCellHover();
  });
}
export function hideCellHover() {
  if (tooltip) tooltip.hidden = true;
}
export function showCellHover(cell, event) {
  if (
    !cell ||
    !cell.visible ||
    event.buttons ||
    event.pointerType === "touch"
  ) {
    hideCellHover();
    return;
  }
  const state = provider();
  if (!state) return;
  if (!tooltip) {
    tooltip = document.createElement("div");
    tooltip.id = "cell-tooltip";
    tooltip.setAttribute("role", "tooltip");
    document.body.append(tooltip);
  }
  tooltip.replaceChildren();
  const title = document.createElement("strong");
  title.textContent = cellLabel(cell, state);
  tooltip.append(title);
  const line = (text) => {
    const p = document.createElement("div");
    p.textContent = text;
    tooltip.append(p);
  };
  if (state.dataSource?.name) line(state.dataSource.name);
  if (state.colorInfo?.source !== "single" && state.colorInfo?.value)
    line(
      `${state.colorInfo.label}: ${state.colorInfo.value(cell) ?? "missing"}`,
    );
  line(`AP ${cell.xyz[0]} · DV ${cell.xyz[1]} · ML ${cell.xyz[2]} µm`);
  tooltip.hidden = false;
  const bounds = tooltip.getBoundingClientRect();
  tooltip.style.left =
    Math.max(8, Math.min(event.clientX + 14, innerWidth - bounds.width - 8)) +
    "px";
  tooltip.style.top =
    Math.max(8, Math.min(event.clientY + 14, innerHeight - bounds.height - 8)) +
    "px";
}
