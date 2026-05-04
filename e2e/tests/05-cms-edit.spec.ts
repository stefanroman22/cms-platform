import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";
import { resetSeedState, getSidCookie } from "../helpers/cleanup";

test.describe("CMS edit + save persistence", () => {
  test.afterEach(async () => {
    const sid = await getSidCookie(
      process.env.E2E_USER_EMAIL!,
      process.env.E2E_USER_PASSWORD!,
    );
    await resetSeedState(sid);
  });

  test("text_block save → reload → value persisted", async ({ page }) => {
    await login(page, process.env.E2E_USER_EMAIL!, process.env.E2E_USER_PASSWORD!);
    await page.goto("/dashboard/e2e-test-project/e2e_text");

    const stamp = `E2E ${Date.now()}`;
    // TextBlockEditor's <label>Title</label> is not associated to the input
    // via htmlFor, so getByLabel("Title") finds nothing. Match by placeholder.
    const titleField = page.getByPlaceholder("Enter section title…");
    await titleField.fill(stamp);

    await page.getByRole("button", { name: /^Save$/ }).click();
    await expect(page.getByText(/Changes saved successfully/i)).toBeVisible();

    await page.reload();
    await expect(page.getByPlaceholder("Enter section title…")).toHaveValue(stamp);
  });
});
