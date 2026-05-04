import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

test.describe("Account page", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, process.env.E2E_USER_EMAIL!, process.env.E2E_USER_PASSWORD!);
    await page.goto("/dashboard/account");
  });

  test("renders profile + appearance + change-password sections", async ({ page }) => {
    // The sidebar nav link "Account Settings" + "Profile" overlap with the
    // <h2> section headings inside the page body. Restrict to heading role.
    await expect(page.getByRole("heading", { name: /Account Settings/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Profile" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Appearance" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Change Password/i })).toBeVisible();
  });

  test("theme toggle flips localStorage value and persists across reload", async ({ page }) => {
    // ThemeShell applies the `dark` class to a wrapper <div>, not <html>,
    // and the source of truth is localStorage("dashboard-theme"). Probe
    // localStorage directly so the test doesn't couple to DOM placement.
    const isDark = () =>
      page.evaluate(() => localStorage.getItem("dashboard-theme") === "dark");
    const initial = await isDark();
    const toggle = page.getByRole("switch", { name: /toggle theme/i });
    await toggle.click();
    await expect.poll(isDark).toBe(!initial);
    await page.reload();
    await page.waitForLoadState("domcontentloaded");
    await expect.poll(isDark, { timeout: 5000 }).toBe(!initial);
    await page.getByRole("switch", { name: /toggle theme/i }).click();
  });
});
