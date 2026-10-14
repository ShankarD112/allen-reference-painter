import { test, expect } from "@playwright/test";
test("searchable guide, text-only branding, and safe cell hover in every live view", async ({
  page,
}, testInfo) => {
  test.setTimeout(180000);
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.locator("#loading")).toBeHidden({ timeout: 60000 });
  await expect(page.locator('link[rel="icon"]')).toHaveAttribute(
    "href",
    "data:,",
  );
  await expect(page.locator(".brand-icon,.local-icon")).toHaveCount(0);
  await page.locator("#help").click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.locator("#help-search").fill("histogram");
  await expect(page.locator("#help-topics details:not([hidden])")).toHaveCount(
    1,
  );
  await expect(page.locator("#help-topics")).toContainText("AND");
  await page.locator("#help-search").fill("zz-no-topic");
  await expect(page.locator("#help-empty")).toBeVisible();
  await page.locator("#help-search").fill("");
  await page.screenshot({
    path: testInfo.outputPath("help-guide.png"),
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();
  await page.locator("#start").click();
  await page.locator('[data-tab="cells"]').click();
  await page.locator("#units").selectOption("um");
  await page
    .locator("#cell-file")
    .setInputFiles({
      name: "hover.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(
        "cell_id,x,y,z,Score,UMAP1,UMAP2\n<AM93>,6600,4000,5700,2.5,1,1\n",
      ),
    });
  await expect(page.locator("#cell-summary")).toContainText("1 of 1");
  await page
    .locator("#color-by")
    .selectOption(JSON.stringify(["metadata", "Score"]));
  const tooltip = page.locator("#cell-tooltip");
  const center = async (selector) => {
    await page.locator(selector).scrollIntoViewIfNeeded();
    const b = await page.locator(selector).boundingBox();
    await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
  };
  await center("#viewer canvas");
  await expect(tooltip).toBeVisible();
  await expect(tooltip).toContainText("cell_id: <AM93>");
  await expect(tooltip).toContainText("Metadata · Score: 2.5");
  await expect(tooltip.locator("am93")).toHaveCount(0);
  await page.screenshot({
    path: testInfo.outputPath("cell-hover.png"),
    fullPage: true,
  });
  await page.mouse.move(1, 1);
  await expect(tooltip).toBeHidden();
  await page
    .getByRole("button", { name: "Locate <AM93>", exact: true })
    .click();
  await expect(page.locator("#coronal-index")).toHaveValue("264");
  await expect(page.locator("#sagittal-index")).toHaveValue("228");
  // Slice center is the atlas midpoint for these coordinates; wait for redraw/load.
  await expect(page.locator("#coronal-position")).toContainText("6,600");
  await expect(page.locator("#coronal")).toHaveAttribute("aria-busy","false");
  await expect(page.locator("#sagittal")).toHaveAttribute("aria-busy","false");
  await center("#coronal");
  await expect(tooltip).toContainText("cell_id: <AM93>");
  await expect(tooltip).toBeVisible();
  await center("#sagittal");
  await expect(tooltip).toBeVisible();
  await page.getByText("Embedding plot", { exact: true }).click();
  await center("#embedding");
  await expect(tooltip).toBeVisible();
  await expect(tooltip).toContainText("hover.csv");
  await page.keyboard.press("Escape");
  await expect(tooltip).toBeHidden();
  await page.locator("#hide-filtered").click();
  await center("#embedding");
  await expect(tooltip).toBeHidden();
  await center("#viewer canvas");
  await expect(tooltip).toBeHidden();
  await page.locator("#show-filtered").click();
  await page
    .locator("#cell-file")
    .setInputFiles({
      name: "labels.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("Name,x,y,z\nFallback label,6600,4000,5700\n"),
    });
  await center("#viewer canvas");
  await expect(tooltip).toContainText("Fallback label");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator("#help").click();
  await page.locator("#help-search").fill("cell IDs");
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.locator("#close-help").click();
  expect(errors).toEqual([]);
});
