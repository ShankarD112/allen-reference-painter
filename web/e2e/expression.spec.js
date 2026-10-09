import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { unzipSync, strFromU8 } from "fflate";
import { Color } from "three";
import { heatColor } from "../core.js";

test("metadata and gene coloring: ID matching, atomic imports, ZIP resume and offline sharing", async ({
  page,
  context,
}, testInfo) => {
  test.setTimeout(180000);
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("dialog", (d) => d.accept());
  await page.goto("/");
  await expect(page.locator("#loading")).toBeHidden({ timeout: 60000 });
  await page.locator("#start").click();
  await page.locator('[data-tab="cells"]').click();
  await page.locator("#units").selectOption("um");
  const cells = {
    name: "cells.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "cell_id,x,y,z,MECvsLEC\nAM93,7716.7,6409.1,1505.5,LEC\nAM94,7410.4,6409.2,1505,LEC\nAM103,9748,5236,1863,MEC\nAM105,7714.9,6405.6,1463.7,LEC\n",
    ),
  };
  await page.locator("#cell-file").setInputFiles(cells);
  await expect(page.locator("#cell-summary")).toContainText("4 of 4");
  await page.locator("#metadata-search").fill("MECvs");
  await page.locator("#apply-metadata").click();
  await expect(page.locator("#active-coloring")).toHaveAttribute(
    "data-source",
    "metadata",
  );
  await expect(page.locator("#category-legend")).toContainText("LEC");
  await expect(page.locator("#category-legend")).toContainText("MEC");
  await page
    .locator("#expression-file")
    .setInputFiles({
      name: "counts.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(
        '"","AM105","AM93","AM103","extra"\n"0610006L08Rik",2.03184,0,1.402177,999\n"OtherGene",0,3,NA,1\n',
      ),
    });
  await expect(page.locator("#expression-summary")).toContainText(
    "2 genes · 3 / 4",
  );
  await page.locator("#gene-search").fill("0610006");
  await expect(page.locator("#active-coloring")).toHaveAttribute(
    "data-source",
    "metadata",
  );
  await page.locator("#apply-gene").click();
  await expect(page.locator("#active-coloring")).toHaveText(
    "Gene · 0610006L08Rik",
  );
  await expect(page.locator("#category-legend")).toBeEmpty();
  await expect(page.locator("#color-range")).toHaveText("02.03184");
  await expect(page.locator("#color-missing")).toContainText(
    "1 cells with missing",
  );
  await page
    .locator("#expression-file")
    .setInputFiles({
      name: "wrong.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("gene,no-match\nG,1\n"),
    });
  await expect(page.locator("#status")).toContainText("No cell IDs match");
  await expect(page.locator("#expression-summary")).toContainText(
    "2 genes · 3 / 4",
  );
  await expect(page.locator("#active-coloring")).toHaveAttribute(
    "data-source",
    "gene",
  );
  await page.locator("#apply-metadata").click();
  await expect(page.locator("#active-coloring")).toHaveAttribute(
    "data-source",
    "metadata",
  );
  await page.locator("#apply-gene").click();
  await page.screenshot({
    path: testInfo.outputPath("gene-coloring.png"),
    fullPage: true,
  });
  await page.locator('[data-tab="export"]').click();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#export-scene").click(),
  ]);
  const bytes = await readFile(await download.path()),
    zip = unzipSync(bytes);
  const saved = JSON.parse(strFromU8(zip["project.json"]));
  expect(saved.coloring).toEqual({ source: "gene", key: "0610006L08Rik" });
  expect(saved.expression.values[0]).toEqual([2.03184, 0, 1.402177, 999]);
  expect(strFromU8(zip["gene_expression.csv"])).toContain("0610006L08Rik");
  const [htmlDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#export-html").click(),
  ]);
  const html = await readFile(await htmlDownload.path(), "utf8");
  const sceneData = JSON.parse(
    html.match(
      /<script id="scene-data" type="application\/json">(.*?)<\/script>/s,
    )[1],
  );
  const points = sceneData.scene.object.children.find(
    (object) => object.type === "Points",
  );
  const colors = sceneData.scene.geometries.find(
    (geometry) => geometry.uuid === points.geometry,
  ).data.attributes.color.array;
  const expected = [
    heatColor(0, [0, 2.03184]),
    "#8799a9",
    heatColor(1.402177, [0, 2.03184]),
    heatColor(2.03184, [0, 2.03184]),
  ].flatMap((value) => new Color(value).toArray());
  colors.forEach((value, i) => expect(value).toBeCloseTo(expected[i], 6));
  const offline = await context.newPage();
  await offline.route("**/*", (route) => route.abort());
  await offline.setContent(html, { waitUntil: "load" });
  await expect(offline.locator("#cell-color-legend")).toContainText(
    "0610006L08Rik",
  );
  await expect(offline.locator("#viewer canvas")).toBeVisible();
  await offline.close();
  await page.locator('[data-tab="cells"]').click();
  await page.locator("#cell-file").setInputFiles(cells);
  await expect(page.locator("#expression-summary")).toHaveText(
    "No expression file loaded.",
  );
  await expect(page.locator("#active-coloring")).toHaveAttribute(
    "data-source",
    "single",
  );
  await page.locator("#cell-color").selectOption("x");
  await page.locator('[data-tab="export"]').click();
  await page
    .locator("#project-file")
    .setInputFiles({
      name: "scene.zip",
      mimeType: "application/zip",
      buffer: bytes,
    });
  await expect(page.locator("#status")).toContainText("Project restored");
  await page.locator('[data-tab="cells"]').click();
  await expect(page.locator("#active-coloring")).toHaveText(
    "Gene · 0610006L08Rik",
  );
  await page.locator("#gene-search").fill("OtherGene");
  await page.locator("#apply-gene").click();
  await expect(page.locator("#active-coloring")).toHaveText("Gene · OtherGene");
  expect(errors).toEqual([]);
});
