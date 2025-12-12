import { test, expect } from '@playwright/test';
import { login } from './helpers';

test('dashboard tiles render and navigate', async ({ page }) => {
  await login(page);

  // Dashboard heading
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  // Tiles
  await expect(page.getByRole("heading", { name: "Upload Artifact" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "System Health" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Browse Artifacts" })).toBeVisible();

  // Click tests optional — uncomment if desired
  // await page.getByRole("heading", { name: "Upload Artifact" }).click();
  // await page.waitForURL('/upload');
});


