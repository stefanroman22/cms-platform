import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { RichText } from "../src/RichText";
import { plainText } from "../src/plainText";
import { splitRichWords } from "../src/splitRichWords";
import { canonicalStyle, parseStyle } from "../src/index";

describe("canonicalStyle (mirrors backend canonical_style)", () => {
  const cases: [string, string | null][] = [
    ["color: #1E5AA8", "color:#1e5aa8"],
    ["color:#abc", "color:#aabbcc"],
    ["color: rgb(30, 90, 168)", "color:#1e5aa8"],
    ['font-family: "Open Sans", Arial, sans-serif', "font-family:'Open Sans'"],
    ["font-size: 1.250em", "font-size:1.25em"],
    ["font-size: 2.0em; color: #000000", "color:#000000;font-size:2em"],
    ["font-size: 11pt", null],
    ["font-size: 9em", null],
    ["color: red", null],
    ["color: url(javascript:alert(1))", null],
    ["font-family: 'Bad;Name'", null],
    ["background: #fff; position: fixed", null],
    ["color:#111111;color:#222222", "color:#222222"],
  ];
  for (const [raw, expected] of cases) it(raw, () => expect(canonicalStyle(raw)).toBe(expected));
});

describe("parseStyle", () => {
  it("splits canonical declarations", () =>
    expect(parseStyle("color:#1e5aa8;font-family:'Open Sans';font-size:1.25em")).toEqual({
      color: "#1e5aa8", fontFamily: "Open Sans", fontSize: "1.25em",
    }));
  it("returns an empty object for nothing valid", () => expect(parseStyle("position:fixed")).toEqual({}));
});

describe("styled spans in the renderer", () => {
  it("RichText renders a styled span", () => {
    const { container } = render(
      <RichText value={'<span style="color:#1e5aa8;font-size:1.5em">Hi</span>'} format="inline" />);
    expect(container.innerHTML).toBe(
      '<span class="cms-rich cms-rich--inline"><span class="cms-rich-style" style="color: rgb(30, 90, 168); font-size: 1.5em;">Hi</span></span>');
  });
  it("font-family falls back to the site body font", () =>
    expect(renderToString(<RichText value={"<span style=\"font-family:'Open Sans'\">x</span>"} format="inline" />)).toContain(
      'style="font-family:&#x27;Open Sans&#x27;, var(--cms-font-body, sans-serif)"'));
  it("a span without a valid style renders its text only", () =>
    expect(render(<RichText value={'<span style="position:fixed">x</span>'} format="inline" />).container.innerHTML).toBe(
      '<span class="cms-rich cms-rich--inline">x</span>'));
  it("plainText of a span value is its text", () =>
    expect(plainText('<span style="color:#1e5aa8">Hi</span> there')).toBe("Hi there"));
  it("splitRichWords keeps the span around each word", () => {
    const words = splitRichWords('<span style="color:#1e5aa8">two words</span>');
    expect(words.map((w) => w.text)).toEqual(["two", "words"]);
    const { container } = render(<>{words.map((w) => <i key={w.key}>{w.node}</i>)}</>);
    expect(container.innerHTML).toBe(
      '<i><span class="cms-rich-style" style="color: rgb(30, 90, 168);">two</span></i>' +
      '<i><span class="cms-rich-style" style="color: rgb(30, 90, 168);">words</span></i>');
  });
});
