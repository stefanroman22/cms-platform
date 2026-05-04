import { Page, expect } from "@playwright/test";

/**
 * Logs the given user in via the /log-in page and waits until the
 * dashboard renders. Returns when the page is ready for assertions.
 */
export async function login(page: Page, email: string, password: string) {
  await page.goto("/log-in");
  await page.getByLabel("Email address or Username").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: /sign in to dashboard/i }).click();
  await expect.poll(async () => {
    const cookies = await page.context().cookies();
    return cookies.some((c) => c.name === "sid");
  }).toBe(true);
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: /projects/i })).toBeVisible();
}

export async function logout(page: Page) {
  await page.goto("/dashboard");
  await page.getByRole("button", { name: /sign out/i }).click();
  await expect(page).toHaveURL(/\/$|\/log-in/);
}
