export async function login(page, username = "ece30861defaultadminuser", password = "adminpassword123!") {
  await page.goto('/login');
  await page.getByPlaceholder("Username").fill(username);
  await page.getByPlaceholder("Password").fill(password);
  await page.getByRole("button", { name: "Sign In" }).click();
  await page.waitForURL('/dashboard');
}
