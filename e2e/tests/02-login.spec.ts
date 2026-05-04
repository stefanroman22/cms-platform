import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

const EMAIL = process.env.E2E_USER_EMAIL!;
const PASSWORD = process.env.E2E_USER_PASSWORD!;

test.describe("Login flow", () => {
  test("happy path — login → dashboard renders", async ({ page }) => {
    await login(page, EMAIL, PASSWORD);
    await expect(page.getByRole("heading", { name: /projects/i })).toBeVisible();
  });

  test("wrong password — error shown, no cookie", async ({ page }) => {
    await page.goto("/log-in");
    await page.getByLabel("Email address or Username").fill(EMAIL);
    await page.getByLabel("Password", { exact: true }).fill("definitely-not-the-password");
    await page.getByRole("button", { name: /sign in to dashboard/i }).click();
    await expect(page.getByText(/Invalid email or password/i)).toBeVisible();
    const cookies = await page.context().cookies();
    expect(cookies.find((c) => c.name === "sid")).toBeUndefined();
  });

  test("logout clears the session", async ({ page }) => {
    await login(page, EMAIL, PASSWORD);
    await page.getByRole("button", { name: /sign out/i }).click();
    await expect(page).toHaveURL(/\/(log-in)?$/);
    const cookies = await page.context().cookies();
    expect(cookies.find((c) => c.name === "sid")).toBeUndefined();
  });
});
