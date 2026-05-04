import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

test.describe("Admin pages", () => {
  test("admin user — All Clients renders e2e users", async ({ page }) => {
    await login(page, process.env.E2E_ADMIN_EMAIL!, process.env.E2E_ADMIN_PASSWORD!);
    await page.goto("/dashboard/admin/clients");
    await expect(page.getByRole("heading", { name: /All Clients/i })).toBeVisible();
    // Email rendered twice (desktop table row + mobile card stack); take .first().
    await expect(page.getByText("e2e-user@cms-test.dev").first()).toBeVisible();
    await expect(page.getByText("e2e-admin@cms-test.dev").first()).toBeVisible();
  });

  test("admin user — All Projects renders e2e-test-project", async ({ page }) => {
    await login(page, process.env.E2E_ADMIN_EMAIL!, process.env.E2E_ADMIN_PASSWORD!);
    await page.goto("/dashboard/admin/projects");
    await expect(page.getByRole("heading", { name: /All Projects/i })).toBeVisible();
    await expect(page.getByText(/E2E Test Project/i)).toBeVisible();
  });

  test("admin user — Service Types renders 8+ types", async ({ page }) => {
    await login(page, process.env.E2E_ADMIN_EMAIL!, process.env.E2E_ADMIN_PASSWORD!);
    await page.goto("/dashboard/admin/service-types");
    await expect(page.getByRole("heading", { name: /Service Types/i })).toBeVisible();
  });

  test("regular user gets blocked / redirected from /dashboard/admin/*", async ({ page }) => {
    await login(page, process.env.E2E_USER_EMAIL!, process.env.E2E_USER_PASSWORD!);
    await page.goto("/dashboard/admin/clients");
    await expect(page.getByText("e2e-admin@cms-test.dev").first()).not.toBeVisible({
      timeout: 5000,
    });
  });
});
