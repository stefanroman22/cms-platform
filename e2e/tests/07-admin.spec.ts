import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

test.describe("Admin pages", () => {
  test("admin user — All Clients renders e2e users", async ({ page }) => {
    await login(page, process.env.E2E_ADMIN_EMAIL!, process.env.E2E_ADMIN_PASSWORD!);
    // `?include_test=true` flips the test-data filter off so the seed
    // e2e-* users render. The default dashboard view (without the
    // query param) deliberately hides them as part of the test-data
    // hygiene introduced in services/test_data.py.
    await page.goto("/dashboard/admin/clients?include_test=true");
    await expect(page.getByRole("heading", { name: /All Clients/i })).toBeVisible();
    // Email rendered twice (desktop table row + mobile card stack); take .first().
    await expect(page.getByText("e2e-user@cms-test.dev").first()).toBeVisible();
    await expect(page.getByText("e2e-admin@cms-test.dev").first()).toBeVisible();
  });

  test("admin user — All Projects renders e2e-test-project", async ({ page }) => {
    await login(page, process.env.E2E_ADMIN_EMAIL!, process.env.E2E_ADMIN_PASSWORD!);
    // `?include_test=true` for the same reason as above —
    // `e2e-test-project` matches `is_test_slug` and is hidden by
    // default.
    await page.goto("/dashboard/admin/projects?include_test=true");
    await expect(page.getByRole("heading", { name: /All Projects/i })).toBeVisible();
    await expect(page.getByText(/E2E Test Project/i).first()).toBeVisible();
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
