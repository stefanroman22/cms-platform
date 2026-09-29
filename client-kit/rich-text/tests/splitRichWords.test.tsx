import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { RichWords, splitRichWords } from "../src/splitRichWords";

describe("splitRichWords", () => {
  it("splits into words that keep their marks", () => {
    const words = splitRichWords("IT <strong>solutions for</strong> you");
    expect(words.map((w) => w.text)).toEqual(["IT", "solutions", "for", "you"]);
    const { container } = render(<>{words.map((w) => <span key={w.key}>{w.node}</span>)}</>);
    expect(container.innerHTML).toBe(
      "<span>IT</span><span><strong>solutions</strong></span><span><strong>for</strong></span><span>you</span>");
  });
  it("glues a word split across a mark boundary", () => {
    expect(splitRichWords("wo<strong>rd</strong> next").map((w) => w.text)).toEqual(["word", "next"]);
  });
  it("marks words after a line break", () => {
    expect(splitRichWords("a<br>b").map((x) => [x.text, x.breakBefore])).toEqual([["a", false], ["b", true]]);
  });
  it("empty value gives no words", () => expect(splitRichWords("")).toEqual([]));
  it("RichWords renders spaces and breaks between words", () => {
    const { container } = render(<RichWords value="a b<br>c" renderWord={(w) => <i>{w.node}</i>} />);
    expect(container.innerHTML).toBe('<span class="cms-rich cms-rich--inline"><i>a</i> <i>b</i><br><i>c</i></span>');
  });
});
