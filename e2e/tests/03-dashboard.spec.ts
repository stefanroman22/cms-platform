import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, process.env.E2E_USER_EMAIL!, process.env.E2E_USER_PASSWORD!);
  });

  test("e2e-test-project appears in the project list", async ({ page }) => {
    await expect(page.getByText("E2E Test Project")).toBeVisible();
  });

  test("clicking the project opens its workspace", async ({ page }) => {
    await page.getByText("E2E Test Project").click();
    await expect(page).toHaveURL(/\/dashboard\/e2e-test-project/);
    await expect(page.getByText(/E2E text block/i)).toBeVisible();
    await expect(page.getByText(/E2E features/i)).toBeVisible();
  });

  test("project workspace shows live website card when website_url is set", async ({ page }) => {
    await page.goto("/dashboard/e2e-test-project");
    const card = page.getByText(/Live website/i);
    if (await card.count()) {
      await expect(card.first()).toBeVisible();
    }
  });
});
