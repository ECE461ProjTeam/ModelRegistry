import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test('system health dashboard loads', async ({ page }) => {
  await login(page);

  await page.goto('/health');
  await expect(page.getByText("System Health")).toBeVisible();

  await page.getByRole("button", { name: "Fetch" }).click();
  await expect(page.getByText("Health Status")).toBeVisible();

  // Check at least one component card
  await expect(page.getByText(/Status:/)).toBeVisible();
});
