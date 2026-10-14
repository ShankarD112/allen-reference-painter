import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
const value = (source, key) => JSON.stringify([source, key]);
test("data handoff, scales, channels, AND filters, summary, Locate and project restore", async ({
  page,
}, testInfo) => {
  test.setTimeout(180000);
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error" && /shader|WebGLProgram/i.test(m.text()))
      errors.push(m.text());
  });
  page.on("dialog", (d) => d.accept());
  await page.goto("/");
  await expect(page.locator("#loading")).toBeHidden({ timeout: 60000 });
  await page.locator("#start").click();
  await page.locator('[data-tab="cells"]').click();
  await page.locator("#example-cells").click();
  await expect(page.locator("#dataset-badge")).toContainText("example_cells");
  await page.locator("#units").selectOption("um");
  await page.locator("#cell-file").setInputFiles({
    name: "my_cells.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "cell_id,x,y,z,Group,Score,UMAP1,UMAP2\na,7700,6400,1500,A,1,0,1\nb,7800,6400,1600,A,2,1,2\nc,7900,6400,1700,B,3,2,1\nd,8000,6400,1800,B,4,3,2\n",
    ),
  });
  await expect(page.locator("#load-upload")).toBeVisible();
  await expect(page.locator("#dataset-badge")).toContainText("example_cells");
  await page.locator("#load-upload").click();
  await expect(page.locator("#dataset-badge")).toHaveText(
    "Showing: my_cells.csv · 4 cells",
  );
  await page.locator("#expression-file").setInputFiles({
    name: "genes.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("gene,d,b,a\nG,9,3,0\nH,1,4,2\n"),
  });
  await expect(page.locator("#expression-summary")).toContainText(
    "2 genes · 3 / 4",
  );
  await expect(page.locator('#color-by optgroup[label="Genes"]')).toHaveCount(
    1,
  );
  await expect(
    page.locator('#color-by optgroup[label="Metadata"]'),
  ).toHaveCount(1);
  await page.locator("#color-by").selectOption(value("gene", "G"));
  await page.locator("#palette").selectOption("magma");
  await page.locator("#clip-min").fill("2");
  await page.locator("#clip-min").dispatchEvent("change");
  await page.locator("#clip-max").fill("5");
  await page.locator("#clip-max").dispatchEvent("change");
  await expect(page.locator("#color-range")).toHaveText("25");
  await page.locator("#palette").selectOption("custom");
  await page.locator("#custom-count").selectOption("2");
  await page.locator("#custom-0").evaluate((node) => {
    node.value = "#000000";
    node.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await page.locator("#custom-1").evaluate((node) => {
    node.value = "#ffffff";
    node.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await page.locator("#shape-by").selectOption("Group");
  await page.locator("#size-by").selectOption(value("metadata", "Score"));
  await expect(page.locator("#shape-legend")).toContainText("A");
  await expect(page.locator("#size-legend")).toContainText("4");
  await page.getByText("Embedding plot", { exact: true }).click();
  await expect(page.locator("#embedding-note")).toContainText("4 visible");
  await page.getByRole("button", { name: "Locate a", exact: true }).click();
  await expect(page.locator("#status")).toContainText("AP 7700");
  await page
    .getByText("Filters · categories and genes", { exact: true })
    .click();
  await page.locator("#filter-gene").selectOption("G");
  await page.locator("#add-gene-filter").click();
  await page.getByLabel("G max value", { exact: true }).fill("4");
  await page.getByLabel("G max value", { exact: true }).dispatchEvent("change");
  await page.locator("#filter-gene").selectOption("H");
  await page.locator("#add-gene-filter").click();
  await page.getByLabel("H min value", { exact: true }).fill("3");
  await page.getByLabel("H min value", { exact: true }).dispatchEvent("change");
  await expect(page.locator("#cell-summary")).toContainText("1 of 4");
  await page.locator("#category-by").selectOption("Group");
  await page.locator("#add-category").click();
  await page.locator("#filter-list").getByLabel("A", { exact: true }).uncheck();
  await expect(page.locator("#cell-summary")).toContainText("0 of 4");
  await page.locator("#filter-list").getByLabel("A", { exact: true }).check();
  await expect(page.locator("#cell-summary")).toContainText("1 of 4");
  await page.getByText("Cell summary", { exact: true }).click();
  await page.locator("#summary-by").selectOption("Group");
  await expect(page.locator("#summary-rows")).toContainText("50.0%");
  await page
    .locator("#summary-rows")
    .getByRole("button", { name: "B", exact: true })
    .click();
  await expect(page.locator("#cell-summary")).toContainText("0 of 4");
  await page.locator("#clear-isolate").click();
  await page.screenshot({
    path: testInfo.outputPath("cell-explorer.png"),
    fullPage: true,
  });
  await page.locator('[data-tab="export"]').click();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#save-project").click(),
  ]);
  const [sharedDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#export-html").click(),
  ]);
  const sharedHTML = await readFile(await sharedDownload.path(), "utf8");
  const scene = JSON.parse(
    sharedHTML.match(
      /<script id="scene-data" type="application\/json">(.*?)<\/script>/s,
    )[1],
  );
  expect(scene.cellColoring.shapeLegend.map((x) => x.label)).toEqual([
    "A",
    "B",
  ]);
  const point = scene.scene.object.children.find((x) => x.type === "Points");
  const attributes = scene.scene.geometries.find(
    (x) => x.uuid === point.geometry,
  ).data.attributes;
  expect(attributes.cellSize.array[0]).toBeCloseTo(1.1, 5);
  const offline = await page.context().newPage();
  offline.on("pageerror", (e) => errors.push(e.message));
  offline.on("console", (m) => {
    if (m.type() === "error" && /shader|WebGLProgram/i.test(m.text()))
      errors.push(m.text());
  });
  await offline.route("**/*", (route) => route.abort());
  await offline.setContent(sharedHTML, { waitUntil: "load" });
  await expect(offline.locator("#cell-color-legend")).toContainText("Shape");
  await expect(offline.locator("#cell-color-legend")).toContainText("Size");
  await expect(offline.locator("#viewer canvas")).toBeVisible();
  await offline.close();
  const saved = await readFile(await download.path());
  const data = JSON.parse(saved);
  expect(data.explorer.genes).toHaveLength(2);
  expect(data.explorer.palette).toBe("custom");
  expect(data.explorer.shape).toBe("Group");
  expect(data.cells.cells[3].manualVisible).toBe(true);
  expect(data.cells.cells[3].visible).toBe(false);
  await page.locator("#project-file").setInputFiles({
    name: "cells.json",
    mimeType: "application/json",
    buffer: saved,
  });
  await expect(page.locator("#status")).toContainText("Project restored");
  await page.locator('[data-tab="cells"]').click();
  await expect(page.locator("#dataset-badge")).toContainText("my_cells.csv");
  await expect(page.locator("#cell-summary")).toContainText("1 of 4");
  await expect(page.locator("#palette")).toHaveValue("custom");
  await page.locator("#clear-filters").click();
  await expect(page.locator("#cell-summary")).toContainText("4 of 4");
  await page.setViewportSize({ width: 390, height: 844 });
  const badge = await page.locator("#dataset-badge").boundingBox();
  const header = await page.locator("header").boundingBox();
  expect(badge.y + badge.height).toBeLessThanOrEqual(header.y + header.height);
  await page.screenshot({
    path: testInfo.outputPath("cell-explorer-mobile.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
test("single HTML contains the complete app code and runs with external atlas data", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const html = await readFile("dist/reference-painter.html", "utf8");
  await page.route("**/single-file-test.html", (route) =>
    route.fulfill({ contentType: "text/html", body: html }),
  );
  await page.goto("/single-file-test.html");
  await expect(page.locator("#loading")).toBeHidden({ timeout: 60000 });
  await page.locator("#start").click();
  await page.locator('[data-tab="cells"]').click();
  await page.locator("#example-cells").click();
  await expect(page.locator("#dataset-badge")).toContainText("96 cells");
  await page.route("**/share/viewer.js", (route) => route.abort());
  await page.locator('[data-tab="export"]').click();
  await Promise.all([
    page.waitForEvent("download"),
    page.locator("#export-html").click(),
  ]);
  expect(await page.locator('script[src],link[rel="stylesheet"]').count()).toBe(
    0,
  );
  expect(errors).toEqual([]);
});
