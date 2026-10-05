export function findRegions(regions, query, mainId = '') {
  const normalized = query.trim().toLowerCase();
  const terms = normalized.split(/\s+/).filter(Boolean);
  return regions.filter(r => r.acronym !== 'root' &&
    (!mainId || r.path.includes(Number(mainId))) &&
    (String(r.id) === normalized || terms.every(term =>
      `${r.acronym} ${r.name}`.toLowerCase().includes(term))))
    .sort((a, b) => a.name.localeCompare(b.name) || a.acronym.localeCompare(b.acronym));
}
