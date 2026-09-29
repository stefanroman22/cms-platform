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
    // Rich-text projects (rich_text_version 1, ADR-0010) edit the title in a
    // TipTap contenteditable (role=textbox, aria-label "Title"); legacy projects
    // keep the plain <input>, matched by placeholder.
    const richTitle = page.getByRole("textbox", { name: "Title" });
    const isRich = (await richTitle.count()) > 0;
    if (isRich) {
      await richTitle.click();
      await page.keyboard.press("Control+A");
      await page.keyboard.type(stamp);
    } else {
      await page.getByPlaceholder("Enter section title…").fill(stamp);
    }

    await page.getByRole("button", { name: /^Save$/ }).click();
    await expect(page.getByText(/Changes saved successfully/i)).toBeVisible();

    await page.reload();
    if (isRich) {
      await expect(page.getByRole("textbox", { name: "Title" })).toHaveText(stamp);
    } else {
      await expect(page.getByPlaceholder("Enter section title…")).toHaveValue(stamp);
    }
  });
});
