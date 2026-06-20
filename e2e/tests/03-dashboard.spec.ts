import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, process.env.E2E_USER_EMAIL!, process.env.E2E_USER_PASSWORD!);
  });

  test("e2e-test-project appears in the sidebar project list", async ({ page }) => {
    await expect(page.getByRole("link", { name: "E2E Test Project" })).toBeVisible();
  });

  test("clicking the project opens its workspace", async ({ page }) => {
    await page.getByRole("link", { name: "E2E Test Project" }).click();
    await expect(page).toHaveURL(/\/dashboard\/e2e-test-project/);
    // The project name renders big at the top; CMS content lives behind the CMS tab.
    await expect(page.getByRole("heading", { name: /E2E Test Project/i })).toBeVisible();
    await page.getByRole("tab", { name: "CMS" }).click();
    await expect(page.getByText(/E2E text block/i)).toBeVisible();
    await expect(page.getByText(/E2E features/i)).toBeVisible();
  });
});
