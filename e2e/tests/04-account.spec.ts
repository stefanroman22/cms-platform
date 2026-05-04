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

  test("theme toggle flips html class and persists across reload", async ({ page }) => {
    const initial = await page.evaluate(() => document.documentElement.classList.contains("dark"));
    const toggle = page.getByRole("switch", { name: /toggle theme/i });
    await toggle.click();
    await expect
      .poll(async () =>
        page.evaluate(() => document.documentElement.classList.contains("dark")),
      )
      .toBe(!initial);
    await page.reload();
    // The theme-init script runs in <head> before hydration but Playwright
    // needs domcontentloaded before reading classList reliably.
    await page.waitForLoadState("domcontentloaded");
    await expect
      .poll(
        async () =>
          page.evaluate(() => document.documentElement.classList.contains("dark")),
        { timeout: 5000 },
      )
      .toBe(!initial);
    await page.getByRole("switch", { name: /toggle theme/i }).click();
  });
});
