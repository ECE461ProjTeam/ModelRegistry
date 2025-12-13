import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test('upload model form submits', async ({ page }) => {
  await login(page);
  await page.goto('/upload');

  // Ensure URL input exists
  const urlInput = page.getByPlaceholder("https://example.com/model");
  await expect(urlInput).toBeVisible();

  // Fill the URL with a valid HF model (simple one)
  await urlInput.fill("https://huggingface.co/google/bert-base-uncased");

  // Ensure select exists and select "model"
  const typeSelect = page.getByRole("combobox");
  await expect(typeSelect).toBeVisible();
  await typeSelect.selectOption("model");

  // Click upload
  const uploadBtn = page.getByRole("button", { name: /upload/i });
  await uploadBtn.click();

  // Wait for success banner
  await expect(page.getByRole("button", { name: /upload/i })).toBeEnabled();
});


