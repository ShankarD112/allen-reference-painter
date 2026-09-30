// Keep 316 MB of generated reference data out of Git. Prepare it at build time.
import { existsSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
const manifest = "public/data/atlas.json";
if (existsSync(manifest)) {
  const data = JSON.parse(readFileSync(manifest, "utf8"));
  if (
    data.atlas === "allen_mouse_25um" &&
    data.atlas_version === "3.1" &&
    data.slices &&
    data.regions.filter((r) => r.file).length === 855 &&
    data.regions
      .filter((r) => r.file)
      .every((r) => existsSync("public/data/" + r.file)) &&
    [0, 2].every((axis) =>
      Array.from({ length: data.atlas_shape[axis] }, (_, i) =>
        existsSync(`public/data/slices/${axis}/${i}.bin.gz`),
      ).every(Boolean),
    )
  ) {
    console.log("Pinned atlas bundle is ready.");
    process.exit(0);
  }
}
function run(cmd, args) {
  const result = spawnSync(cmd, args, { stdio: "inherit" });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status || 1);
}
const python = process.env.PAINTER_PYTHON || "python3";
run(python, ["-m", "venv", ".atlas-venv"]);
const venv =
  process.platform === "win32"
    ? ".atlas-venv/Scripts/python.exe"
    : ".atlas-venv/bin/python";
run(venv, ["-m", "pip", "install", "-r", "requirements-web.txt"]);
run(venv, ["scripts/build_web_atlas.py", "--cache", ".atlas-cache"]);
