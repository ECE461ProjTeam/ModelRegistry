import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test('admin reset page loads', async ({ page }) => {
  await login(page);

  await page.goto('/admin/reset');
  await expect(page.getByText("Admin Reset")).toBeVisible();
  await expect(page.getByRole("button", { name: "Reset Registry" })).toBeVisible();
});
