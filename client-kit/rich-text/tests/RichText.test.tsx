import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import type { ReactElement } from "react";
import { RichText } from "../src/RichText";

const html = (ui: ReactElement) => render(ui).container.innerHTML;

describe("RichText", () => {
  it("renders semantic elements inside .cms-rich", () => {
    expect(html(<RichText value="<p>Hi <strong>there</strong></p><ul><li><p>a</p></li></ul>" />)).toBe(
      '<div class="cms-rich"><p>Hi <strong>there</strong></p><ul><li><p>a</p></li></ul></div>');
  });
  it("inline format renders a span wrapper", () => {
    expect(html(<RichText value="A &amp; <em>B</em>" format="inline" />)).toBe(
      '<span class="cms-rich cms-rich--inline">A &amp; <em>B</em></span>');
  });
  it("renders nothing for empty, whitespace or empty-paragraph values", () => {
    for (const v of ["", "   ", "<p></p>", "<p><br></p>", null, undefined]) {
      expect(render(<RichText value={v} />).container.innerHTML).toBe("");
    }
  });
  it("renders legacy markdown rich values", () => {
    expect(html(<RichText value={"**Bold** text\n\n- one"} />)).toBe(
      '<div class="cms-rich"><p><strong>Bold</strong> text</p><ul><li><p>one</p></li></ul></div>');
  });
  it("decodes entities exactly once", () => {
    // Expression container, not a JSX string-literal attribute: double-quoted
    // JSX attribute literals are themselves HTML-entity-decoded at compile
    // time (JSXAttributeValue follows JSXText's character grammar), which
    // would silently consume one decode pass before RichText ever saw the
    // value and make this assert our own decodeEntities was skipped instead
    // of run once.
    expect(render(<RichText value={"Tom &amp;amp; Jerry"} format="inline" />).container.textContent).toBe("Tom &amp; Jerry");
  });
  it("never renders scripts, handlers or javascript: links", () => {
    const out = html(<RichText value={'<p onclick="x()">a<script>alert(1)</script><img src=x onerror=y><a href="javascript:z()">l</a></p>'} />);
    expect(out).toBe('<div class="cms-rich"><p>al</p></div>');
  });
  it("external links open in a new tab, internal and mailto ones don't", () => {
    const out = html(<RichText value={'<p><a href="https://x.ro">e</a> <a href="/c">i</a> <a href="mailto:a@b.ro">m</a></p>'} />);
    expect(out).toContain('<a href="https://x.ro" target="_blank" rel="noopener noreferrer">e</a>');
    expect(out).toContain('<a href="/c">i</a>');
    expect(out).toContain('<a href="mailto:a@b.ro">m</a>');
  });
  it("links={false} renders no anchors (safe inside clickable cards)", () => {
    expect(html(<RichText value={'<a href="https://x.ro">t</a>'} format="inline" links={false} />)).toBe(
      '<span class="cms-rich cms-rich--inline"><span class="cms-rich-link">t</span></span>');
  });
  it("renderLink is used for internal links", () => {
    const out = html(<RichText value={'<a href="/about">t</a>'} format="inline"
      renderLink={({ href, children }) => <a data-router="" href={href}>{children}</a>} />);
    expect(out).toContain('<a data-router="" href="/about">t</a>');
  });
  it("headingOffset shifts levels and clamps at h6", () => {
    expect(html(<RichText value="<h2>a</h2><h4>b</h4>" headingOffset={1} />)).toBe('<div class="cms-rich"><h3>a</h3><h5>b</h5></div>');
    expect(html(<RichText value="<h4>b</h4>" headingOffset={5} />)).toBe('<div class="cms-rich"><h6>b</h6></div>');
  });
  it("keeps interior empty paragraphs", () => {
    expect(html(<RichText value="<p>a</p><p></p><p>b</p>" />)).toBe('<div class="cms-rich"><p>a</p><p></p><p>b</p></div>');
  });
  it("server render is deterministic (no hydration mismatch)", () => {
    const v = '<p>a<br>b &amp; <a href="https://x.ro">c</a></p><ol><li><p>x</p></li></ol>';
    expect(renderToString(<RichText value={v} />)).toBe(renderToString(<RichText value={v} />));
  });
  it("accepts className, id and as", () => {
    expect(html(<RichText value="<p>x</p>" as="section" className="prose" id="s" />)).toBe(
      '<section class="cms-rich prose" id="s"><p>x</p></section>');
  });
});
