import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test('profile page loads and user info shows', async ({ page }) => {
  await login(page);

  await page.goto('/user');
  await expect(page.getByText("User Profile")).toBeVisible();
  await expect(page.getByText("Permissions")).toBeVisible();
});

test('admin can search users', async ({ page }) => {
  await login(page);

  await page.goto('/user');
  await page.getByPlaceholder("Search users...").fill("ece");
  await expect(page.locator(".card")).toBeVisible();
});
