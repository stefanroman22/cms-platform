import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";
import { resetSeedState, getSidCookie } from "../helpers/cleanup";

test.describe("Publish flow", () => {
  test.afterEach(async () => {
    const sid = await getSidCookie(
      process.env.E2E_USER_EMAIL!,
      process.env.E2E_USER_PASSWORD!,
    );
    await resetSeedState(sid);
  });

  test("edit → save → publish → public /content reflects", async ({ page, request }) => {
    await login(page, process.env.E2E_USER_EMAIL!, process.env.E2E_USER_PASSWORD!);
    await page.goto("/dashboard/e2e-test-project/e2e_text");

    const stamp = `Published ${Date.now()}`;
    await page.getByPlaceholder("Enter section title…").fill(stamp);
    await page.getByRole("button", { name: /^Save$/ }).click();
    await expect(page.getByText(/Changes saved successfully/i)).toBeVisible();

    await page.getByRole("button", { name: /publish changes/i }).click();
    await page.getByRole("button", { name: /^Publish$/ }).click();

    const backend = process.env.E2E_BASE_URL_BACKEND!;
    await expect.poll(async () => {
      const resp = await request.get(`${backend}/content/e2e-test-project`);
      if (!resp.ok()) return null;
      const body = await resp.json();
      return body.content?.e2e_text?.title;
    }, { timeout: 60_000, intervals: [2000, 5000, 10_000] }).toBe(stamp);
  });
});
