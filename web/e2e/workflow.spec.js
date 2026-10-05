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
  await page.locator("#start").click();
  await page.locator("#search").fill("ENT");
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
  if (await page.locator("#start").isVisible()) await page.locator("#start").click();
  await page.locator('[data-tab="cells"]').click();
  await page.locator("#example-cells").click();
  await page.locator("#cell-color").selectOption("Tau");
  await expect(page.locator("#cell-summary")).toContainText("96 of 96");
  await page.locator("#cell-filter").fill("Cell 02");
  await page.locator("#hide-filtered").click();
  await expect(page.locator("#cell-summary")).toContainText("95 of 96");
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
  expect(sceneManifest.selected_cell_count).toBe(95);
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
  await page.locator("#project-file").setInputFiles({name:"project.json",mimeType:"application/json",buffer:await readFile(saved)});
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
  if (await page.locator("#start").isVisible()) await page.locator("#start").click();
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
  await expect(page.locator("#cell-summary")).toContainText("96 of 96");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await expect(page.locator("#viewer canvas")).toBeVisible();
});

test('home, alphabetic regions, labeled ZIP resume/merge and standalone offline HTML', async ({ page, context }, testInfo) => {
  test.setTimeout(180000);
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('dialog', d => d.accept());
  await page.goto('/');
  await expect(page.locator('#loading')).toBeHidden({ timeout:60000 });
  await expect(page.locator('#home-screen')).toBeVisible();
  await expect(page.locator('.sidebar')).toBeHidden();
  await page.screenshot({path:testInfo.outputPath('home.png')});
  await page.locator('#start').click();
  const names = await page.locator('#search-results small').allTextContents();
  const clean = names.map(n => n.replace(' · mesh unavailable',''));
  expect(clean).toEqual([...clean].sort((a,b) => a.localeCompare(b)));
  await page.locator('#main-region').selectOption({label:'Hippocampal formation'});
  expect(await page.locator('#search-results button').count()).toBeLessThan(names.length);
  await page.locator('#main-region').selectOption('');
  await page.locator('#search').fill('ENT');
  await page.getByRole('button',{name:'Load ENT — Entorhinal area',exact:true}).click();
  await expect(page.locator('#active-title')).toHaveText('ENT');
  await page.locator('[data-tab="paint"]').click();
  await page.locator('#layer-name').fill('Injection site');
  await page.locator('#layer-name').press('Tab');
  await page.locator('#layer-tags').fill('animal-01, treatment');
  await page.locator('#layer-tags').press('Tab');
  await page.locator('[data-mask="fill"]').click();
  const count = await page.locator('#face-count').textContent();
  expect(Number(count.replaceAll(',',''))).toBeGreaterThan(0);
  await page.locator('#add-layer').click();
  await page.locator('#layer-name').fill('Control'); await page.locator('#layer-name').press('Tab');
  await page.locator('[data-mask="fill"]').click();
  await page.locator('#paint-color').evaluate(el => { el.value = '#00ccff'; el.dispatchEvent(new Event('input')); });
  await page.screenshot({path:testInfo.outputPath('opaque-paint.png')});
  await page.locator('[data-tab="export"]').click();
  const [roi] = await Promise.all([page.waitForEvent('download'),page.locator('#export-roi').click()]);
  const bytes = await readFile(await roi.path());
  const project = JSON.parse(strFromU8(unzipSync(new Uint8Array(bytes))['project.json']));
  expect(project.version).toBe(2); expect(project.regions[0].layers).toHaveLength(2);
  expect(project.regions[0].layers[0].tags).toBe('animal-01, treatment');
  const file = {name:'animal-01.zip',mimeType:'application/zip',buffer:bytes};
  await page.locator('#project-file').setInputFiles(file);
  await expect(page.locator('#status')).toContainText('Project restored');
  await page.locator('#import-mode').selectOption('merge');
  await page.locator('#project-file').setInputFiles([file,{...file,name:'animal-02.zip'}]);
  await expect(page.locator('#status')).toContainText('Project restored');
  await page.locator('[data-tab="paint"]').click();
  await expect(page.locator('.layer-row')).toHaveCount(6);
  await page.locator('#layer-filter').fill('animal-02'); await expect(page.locator('.layer-row')).toHaveCount(2);
  await page.locator('#layer-filter').fill('');
  await page.locator('#isolate-layer').click();
  await expect(page.locator('.layer-row input:checked')).toHaveCount(1);
  await expect(page.locator('#coronal')).toBeVisible();
  const canvas = page.locator('#coronal'); const box = await canvas.boundingBox();
  await page.mouse.move(box.x + box.width/2,box.y + box.height/2);
  await expect(page.locator('#slice-hover')).toContainText('AP ');
  await expect(page.locator('#slice-hover')).toContainText('DV ');
  await expect(page.locator('#slice-hover')).toContainText('ML ');
  await page.locator('[data-tab="export"]').click();
  const [html] = await Promise.all([page.waitForEvent('download'),page.locator('#export-html').click()]);
  const htmlPath = testInfo.outputPath('scene.html'); await html.saveAs(htmlPath);
  const shared = await context.newPage();
  shared.on('pageerror',e => errors.push(e.message));
  await shared.route(/^https?:/,route => route.abort());
  await shared.goto('file://' + htmlPath);
  await expect(shared.locator('#viewer canvas')).toBeVisible();
  await expect(shared.locator('#legend')).toContainText('Injection site');
  await shared.locator('#filter').fill('animal-02');
  await expect(shared.locator('#legend label:visible')).toHaveCount(2);
  await shared.locator('#reset').click();
  await shared.screenshot({path:testInfo.outputPath('offline-html.png')});
  await shared.close();
  await page.locator('[data-tab="regions"]').click();
  await page.locator('#remove-all').click();
  await expect(page.locator('#region-count')).toHaveText('0');
  await page.locator('#search').fill('Entorhinal area, lateral part, layer 1');
  await page.locator('#load-all').click();
  await expect(page.locator('#status')).toHaveText('Matching meshes loaded.');
  await expect(page.locator('#region-count')).toHaveText('1');
  expect(errors).toEqual([]);
});
