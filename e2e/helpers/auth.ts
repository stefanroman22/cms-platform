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
  // /dashboard no longer renders a projects overview — it redirects to the
  // last-visited (or first) project workspace, or stays put with an empty
  // state for users who own no projects (e.g. the e2e admin). The sidebar's
  // "Projects" chapter is the stable post-login landmark either way.
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/dashboard(\/[^/?]+)?$/);
  await expect(page.getByText("Projects", { exact: true }).first()).toBeVisible();
}

export async function logout(page: Page) {
  await page.goto("/dashboard");
  await page.getByRole("button", { name: /sign out/i }).click();
  await expect(page).toHaveURL(/\/$|\/log-in/);
}
