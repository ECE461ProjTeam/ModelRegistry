import { test, expect } from '@playwright/test';
import { login } from './helpers';

test('artifact list loads and clicking row navigates', async ({ page }) => {
  await login(page);

  await page.goto('/artifacts');
  await expect(page.getByRole("heading", { name: "Artifacts" })).toBeVisible();

  const rows = page.locator("tbody tr");
  const count = await rows.count();

  if (count === 0) {
    console.log("⚠ No artifacts found — skipping row click test");
    test.skip();
  }

  await rows.first().click();
  await expect(page.getByRole("heading", { name: "Artifact Details" })).toBeVisible();
});

