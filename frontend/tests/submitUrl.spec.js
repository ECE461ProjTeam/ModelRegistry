import { test, expect } from '@playwright/test';

test('shows validation error when URL is empty', async ({ page }) => {
  await page.goto('http://localhost:5173');
  await page.click('#submit-btn');
  await expect(page.locator('#status-text')).toHaveText(/Please enter a valid URL/i);
});

test('shows validation error for invalid URL format', async ({ page }) => {
  await page.goto('http://localhost:5173');
  await page.fill('#url-input', 'invalid_url');
  await page.click('#submit-btn');
  await expect(page.locator('#status-text')).toHaveText(/Please enter a valid URL format/i);
});

test('shows submitting state when submitting a valid URL', async ({ page }) => {
  await page.goto('http://localhost:5173');
  await page.fill('#url-input', 'https://example.com');
  await page.click('#submit-btn');
  await expect(page.locator('#submit-btn')).toHaveText(/Submitting/i);
});
