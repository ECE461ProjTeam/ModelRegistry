import { test, expect } from '@playwright/test';
import { login } from './helpers';

test('admin can access admin reset page', async ({ page }) => {
  await login(page);
  await page.goto('/admin/reset');
  await expect(page.getByRole("heading", { name: "Admin Reset" })).toBeVisible();
});

test('non-admin cannot access admin features', async ({ page }) => {
  await page.goto('/login');
  await page.getByPlaceholder("Username").fill("user");
  await page.getByPlaceholder("Password").fill("password123");
  await page.getByRole("button", { name: "Sign In" }).click();

  await page.goto('/admin/reset');
  await page.waitForURL(/dashboard|login/);
});
