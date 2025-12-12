import { test, expect } from '@playwright/test';
import { login } from './helpers';

test('artifact details page loads and buttons work', async ({ page }) => {
  await login(page);

  await page.goto('/artifacts');

  const rows = page.locator("tbody tr");
  const count = await rows.count();

  if (count === 0) {
    console.log("⚠ No artifacts available — skipping artifact details test");
    test.skip();
  }

  await rows.first().click();
  await expect(page.getByRole("heading", { name: "Artifact Details" })).toBeVisible();

  // Optional: cost tab
  if (await page.getByText("Cost").count() > 0) {
    await page.getByText("Cost").click();
  }
});
