import { test, expect } from '@playwright/test';
import { login } from './helpers';

test('successful login takes you to dashboard', async ({ page }) => {
  await login(page);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
});

test('invalid credentials show error', async ({ page }) => {
  await page.goto('/login');
  await page.getByPlaceholder("Username").fill("wrong");
  await page.getByPlaceholder("Password").fill("wrong");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page.getByText(/invalid/i)).toBeVisible();
});

test('protected route redirects to login', async ({ page }) => {
  await page.goto('/dashboard');
  await page.waitForURL(/login/);
  await expect(page.getByPlaceholder("Username")).toBeVisible();
});

