import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { EditingSectionProvider } from "../../context/EditingSectionContext";
import { DesignPromptSection } from "../DesignPromptSection";
import type { Lead } from "../../types";

// SEC-059: record every string handed to DOMPurify.sanitize (delegating to the
// real implementation) so we can assert the Copy path sanitizes the raw,
// agent-written HTML before it reaches innerHTML.
const sanitizeCalls: string[] = [];
vi.mock("isomorphic-dompurify", async (importOriginal) => {
  const mod = await importOriginal<typeof import("isomorphic-dompurify")>();
  const real = mod.default;
  const sanitize = (dirty: string, ...rest: unknown[]) => {
    sanitizeCalls.push(dirty);
    return (real.sanitize as (...a: unknown[]) => string)(dirty, ...rest);
  };
  return { ...mod, default: { ...real, sanitize } };
});

// Replace TipTap with a simple textarea — tests don't need the real editor.
vi.mock("../DesignPromptEditor", () => ({
  DesignPromptEditor: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <textarea
      aria-label="Design prompt editor"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  ),
}));

const lead = { id: "lead-1", design_prompt: "<p>brief</p>" } as unknown as Lead;

describe("DesignPromptSection", () => {
  it("renders read view with stored HTML", () => {
    render(
      <EditingSectionProvider>
        <DesignPromptSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>
    );
    expect(screen.getByText("brief")).toBeTruthy();
  });

  it("reveals the editor on pencil click", () => {
    render(
      <EditingSectionProvider>
        <DesignPromptSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>
    );
    fireEvent.click(screen.getByLabelText("Edit Design prompt"));
    expect(screen.getByLabelText("Design prompt editor")).toBeTruthy();
  });

  // SEC-059: the Copy button runs the raw, agent-written design_prompt through
  // htmlToPlainText, which assigns it to innerHTML on a node appended to the live
  // document. Without sanitization, markup handlers (<img onerror>/<svg onload>)
  // execute in the admin origin. Verify the raw HTML is routed through DOMPurify
  // (and dangerous handlers stripped) before it ever reaches innerHTML.
  it("sanitizes agent-written HTML before copying (no active onerror handler)", async () => {
    const malicious =
      "<p>brief</p><img src=x onerror=\"window.__xss_fired=(window.__xss_fired||0)+1\">";
    const xssLead = { id: "lead-2", design_prompt: malicious } as unknown as Lead;

    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    (window as unknown as { __xss_fired?: number }).__xss_fired = 0;
    sanitizeCalls.length = 0;

    render(
      <EditingSectionProvider>
        <DesignPromptSection lead={xssLead} onPatched={vi.fn()} />
      </EditingSectionProvider>
    );

    // Baseline: the render preview already sanitizes; drop those calls so the
    // assertion below is specifically about the Copy click path.
    sanitizeCalls.length = 0;

    fireEvent.click(screen.getByLabelText("Copy design prompt"));

    // htmlToPlainText sanitizes synchronously (before innerHTML) inside the click
    // handler, so the raw payload is recorded immediately. (jsdom does not
    // implement innerText, so the clipboard write itself is a no-op here; what
    // matters for SEC-059 is that the raw HTML is sanitized before innerHTML.)
    await waitFor(() => expect(sanitizeCalls.length).toBeGreaterThan(0));

    // The raw, unsanitized payload must have been routed through DOMPurify on the
    // copy path (this is exactly what was missing before the fix).
    expect(sanitizeCalls).toContain(malicious);

    // Sanitized output drops the onerror handler entirely, and the injected
    // handler never fired in the admin origin.
    const { default: DOMPurify } = await import("isomorphic-dompurify");
    expect(DOMPurify.sanitize(malicious)).not.toContain("onerror");
    expect((window as unknown as { __xss_fired?: number }).__xss_fired).toBe(0);
  });
});
