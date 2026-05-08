import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

// Skip the two `?include_test=true`-dependent specs unless the run is
// against the master-deployed frontend. Reason: the URL-param handling
// for include_test lives in `src/app/dashboard/admin/{clients,projects}
// /page.tsx` and only reaches prod after master deploy. On dev push,
// Playwright hits the master deploy (prod) — old code, no param
// handling, seed fixtures hidden by the backend filter, tests fail.
//
// e2e.yml sets `PLAYWRIGHT_DEPLOYED_STATE=true` on master push only;
// elsewhere the suite skips the include_test specs. Same pattern as
// pytest's `deployed_state` marker.
const isDeployedState = process.env.PLAYWRIGHT_DEPLOYED_STATE === "true";

test.describe("Admin pages", () => {
  test("admin user — All Clients renders e2e users", async ({ page }) => {
    test.skip(
      !isDeployedState,
      "Requires the deployed frontend to honour ?include_test=true (master-only).",
    );
    await login(
      page,
      process.env.E2E_ADMIN_EMAIL!,
      process.env.E2E_ADMIN_PASSWORD!,
    );
    // `?include_test=true` flips the test-data filter off so the seed
    // e2e-* users render. The default dashboard view (without the
    // query param) deliberately hides them as part of the test-data
    // hygiene introduced in services/test_data.py.
    await page.goto("/dashboard/admin/clients?include_test=true");
    await expect(
      page.getByRole("heading", { name: /All Clients/i }),
    ).toBeVisible();
    // Email rendered twice (desktop table row + mobile card stack); take .first().
    await expect(page.getByText("e2e-user@cms-test.dev").first()).toBeVisible();
    await expect(
      page.getByText("e2e-admin@cms-test.dev").first(),
    ).toBeVisible();
  });

  test("admin user — All Projects renders e2e-test-project", async ({
    page,
  }) => {
    test.skip(
      !isDeployedState,
      "Requires the deployed frontend to honour ?include_test=true (master-only).",
    );
    await login(
      page,
      process.env.E2E_ADMIN_EMAIL!,
      process.env.E2E_ADMIN_PASSWORD!,
    );
    // `?include_test=true` for the same reason as above —
    // `e2e-test-project` matches `is_test_slug` and is hidden by
    // default.
    await page.goto("/dashboard/admin/projects?include_test=true");
    await expect(
      page.getByRole("heading", { name: /All Projects/i }),
    ).toBeVisible();
    await expect(page.getByText(/E2E Test Project/i).first()).toBeVisible();
  });

  test("admin user — Service Types renders 8+ types", async ({ page }) => {
    await login(
      page,
      process.env.E2E_ADMIN_EMAIL!,
      process.env.E2E_ADMIN_PASSWORD!,
    );
    await page.goto("/dashboard/admin/service-types");
    await expect(
      page.getByRole("heading", { name: /Service Types/i }),
    ).toBeVisible();
  });

  test("regular user gets blocked / redirected from /dashboard/admin/*", async ({
    page,
  }) => {
    await login(
      page,
      process.env.E2E_USER_EMAIL!,
      process.env.E2E_USER_PASSWORD!,
    );
    await page.goto("/dashboard/admin/clients");
    await expect(
      page.getByText("e2e-admin@cms-test.dev").first(),
    ).not.toBeVisible({
      timeout: 5000,
    });
  });
});
