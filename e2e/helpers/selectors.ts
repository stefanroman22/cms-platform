/**
 * Shared selectors — keeps tests readable. Always prefer role/label
 * over CSS classes (Tailwind classes are not stable contracts).
 */
import { Page } from "@playwright/test";

export const heading = (page: Page, name: RegExp | string) =>
  page.getByRole("heading", { name });

export const button = (page: Page, name: RegExp | string) =>
  page.getByRole("button", { name });

export const link = (page: Page, name: RegExp | string) =>
  page.getByRole("link", { name });

export const textInput = (page: Page, label: RegExp | string) =>
  page.getByLabel(label);
