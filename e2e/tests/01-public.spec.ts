import { test, expect } from "@playwright/test";

test.describe("Public pages — render without DOM errors", () => {
  test("landing / loads and has no console errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await page.goto("/");
    await expect(page).toHaveTitle(/.+/);
    await expect(page.locator("body")).toBeVisible();
    expect(errors, `Console/page errors:\n${errors.join("\n")}`).toEqual([]);
  });

  test("/log-in renders form fields", async ({ page }) => {
    await page.goto("/log-in");
    await expect(page.getByLabel("Email address or Username")).toBeVisible();
    await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: /sign in to dashboard/i })).toBeVisible();
  });
});
