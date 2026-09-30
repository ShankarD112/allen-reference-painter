import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { unzipSync, strFromU8 } from "fflate";

test("real atlas: search, paint, mirror, undo, cells, export and project reload", async ({
  page,
}, testInfo) => {
  const errors = [];
  page.on("pageerror", (err) => errors.push(err.message));
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("/");
  await expect(page.locator("#loading")).toBeHidden({ timeout: 60000 });
  await page
    .getByRole("button", { name: "Load ENT — Entorhinal area", exact: true })
    .click();
  await expect(page.locator("#active-title")).toHaveText("ENT");
  await expect(page.locator("#status")).toContainText("original mesh faces");
  await page
    .getByRole("button", { name: "Paint", exact: true })
    .first()
    .click();
  await page.locator('[data-mode="paint"]').click();
  await page.locator("#mirror").check();
  const canvas = page.locator("#viewer canvas"),
    box = await canvas.boundingBox();
  // Find a visible surface through actual pointer events, then stroke across it.
  let painted = false;
  for (const xf of [0.3, 0.4, 0.6, 0.7, 0.5, 0.2, 0.8]) {
    for (const yf of [0.5, 0.4, 0.6, 0.3, 0.7]) {
      await page.mouse.click(box.x + box.width * xf, box.y + box.height * yf);
      if (
        Number(
          (await page.locator("#face-count").textContent()).replaceAll(",", ""),
        ) > 0
      ) {
        painted = true;
        break;
      }
    }
    if (painted) break;
  }
  expect(painted).toBe(true);
  const count = await page.locator("#face-count").textContent();
  await page.locator("#undo").click();
  await expect(page.locator("#face-count")).toHaveText("0");
  await page.locator("#redo").click();
  await expect(page.locator("#face-count")).toHaveText(count);
  await page.locator('[data-tab="cells"]').click();
  await page.locator("#example-cells").click();
  await page.locator("#cell-color").selectOption("Tau");
  await expect(page.locator("#cell-summary")).toContainText("3 of 3");
  await page.locator("#cell-filter").fill("Cell 02");
  await page.locator("#hide-filtered").click();
  await expect(page.locator("#cell-summary")).toContainText("2 of 3");
  await page.locator('[data-tab="export"]').click();
  const [roi] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#export-roi").click(),
  ]);
  const zip = unzipSync(new Uint8Array(await readFile(await roi.path())));
  const meta = JSON.parse(
    strFromU8(zip[Object.keys(zip).find((k) => k.endsWith("_metadata.json"))]),
  );
  expect(meta.axis_order).toEqual(["AP", "DV", "ML"]);
  expect(meta.mirrored_face_ids.length).toBeGreaterThan(0);
  expect(meta.n_painted_faces).toBe(Number(count.replaceAll(",", "")));
  const [scene] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#export-scene").click(),
  ]);
  const sceneZip = unzipSync(
    new Uint8Array(await readFile(await scene.path())),
  );
  const sceneManifest = JSON.parse(strFromU8(sceneZip["scene_manifest.json"]));
  expect(sceneManifest.selected_cell_count).toBe(2);
  expect(strFromU8(sceneZip[sceneManifest.cells_file])).toContain("app_x_um");
  const [project] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#save-project").click(),
  ]);
  const saved = await project.path();
  await page.locator('[data-tab="paint"]').click();
  await page.locator("#clear-roi").click();
  await expect(page.locator("#face-count")).toHaveText("0");
  await page.locator('[data-tab="export"]').click();
  await page.locator("#project-file").setInputFiles(saved);
  await expect(page.locator("#status")).toContainText("Project restored");
  await page.locator('[data-tab="paint"]').click();
  await expect(page.locator("#face-count")).toHaveText(count);
  await page.locator("#coronal-index").fill("320");
  await page.locator("#coronal-index").dispatchEvent("change");
  await expect(page.locator("#coronal-position")).toContainText("8,000");
  await page.screenshot({
    path: testInfo.outputPath("workspace.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("invalid cell coordinates do not replace an existing table; mobile layout fits", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator("#loading")).toBeHidden({ timeout: 60000 });
  await page.locator('[data-tab="cells"]').click();
  await page.locator("#example-cells").click();
  await page
    .locator("#cell-file")
    .setInputFiles({
      name: "bad.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("AP,DV,ML\n1,,3\n"),
    });
  await expect(page.locator("#status")).toContainText("Invalid coordinates");
  await expect(page.locator("#cell-summary")).toContainText("3 of 3");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await expect(page.locator("#viewer canvas")).toBeVisible();
});
