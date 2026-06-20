// Vitest mock for @/i18n/navigation — replaces next-intl/navigation hooks
// that require next/navigation (unavailable in jsdom).
import { vi } from "vitest";
import { createElement, type ReactNode } from "react";

export const usePathname = vi.fn(() => "/");
export const useRouter = vi.fn(() => ({ replace: vi.fn(), push: vi.fn() }));
export const Link = ({
  href,
  children,
  ...rest
}: {
  href: string;
  children: ReactNode;
  [key: string]: unknown;
}) => createElement("a", { href, ...rest }, children);
export const redirect = vi.fn();
export const getPathname = vi.fn(() => "/");
