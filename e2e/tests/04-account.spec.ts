import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

test.describe("Account page", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, process.env.E2E_USER_EMAIL!, process.env.E2E_USER_PASSWORD!);
    await page.goto("/dashboard/account");
  });

  test("renders profile + appearance + change-password sections", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /Account Settings/i })).toBeVisible();
    await expect(page.getByText(/Profile/i)).toBeVisible();
    await expect(page.getByText(/Appearance/i)).toBeVisible();
    await expect(page.getByText(/Change Password/i)).toBeVisible();
  });

  test("theme toggle flips html class and persists across reload", async ({ page }) => {
    const initial = await page.evaluate(() => document.documentElement.classList.contains("dark"));
    const toggle = page.getByRole("switch", { name: /toggle theme/i });
    await toggle.click();
    await expect.poll(async () =>
      page.evaluate(() => document.documentElement.classList.contains("dark")),
    ).toBe(!initial);
    await page.reload();
    const afterReload = await page.evaluate(() =>
      document.documentElement.classList.contains("dark"),
    );
    expect(afterReload).toBe(!initial);
    await page.getByRole("switch", { name: /toggle theme/i }).click();
  });
});
