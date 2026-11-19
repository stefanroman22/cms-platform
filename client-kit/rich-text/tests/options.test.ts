import { describe, expect, it } from "vitest";
import { inkOn, readColor, readOptionFields, readOptions, readToggle } from "../src/options";

const schema = [
  { key: "show_title", label: "Show title", type: "toggle", default: true },
  { key: "content_width", label: "Content width", type: "select", default: "normal",
    options: [{ value: "narrow", label: "Narrow" }, { value: "normal", label: "Normal" }, { value: "wide", label: "Wide" }] },
  { key: "background", label: "Background", type: "color", default: "" },
];
const svc = (values: Record<string, unknown>, s: unknown = schema) => ({ _type: "options", _label: "Home", _schema: s, values });
const defaults = { show_title: true, content_width: "normal", background: "" };

describe("readColor", () => {
  it("lowercases a 6-digit hex", () => expect(readColor("#1E5AA8")).toBe("#1e5aa8"));
  it("rejects everything else", () => {
    for (const v of ["#fff", "1e5aa8", "#1e5aa8ff", "red", "rgb(0,0,0)", "#1e5aa8;x:y", "", null, 1, {}]) {
      expect(readColor(v)).toBe("");
    }
  });
});

describe("readToggle", () => {
  it("returns a real boolean", () => {
    expect(readToggle(false, true)).toBe(false);
    expect(readToggle(true, false)).toBe(true);
  });
  it("falls back for non-booleans", () => {
    for (const v of ["false", "true", 0, 1, null, undefined]) expect(readToggle(v, true)).toBe(true);
  });
});

describe("readOptionFields", () => {
  it("keeps well-formed fields", () => expect(readOptionFields(schema)).toEqual(schema));
  it("returns [] for a non-array", () => {
    expect(readOptionFields(undefined)).toEqual([]);
    expect(readOptionFields({ key: "x" })).toEqual([]);
  });
  it("skips other types and malformed entries", () => {
    expect(readOptionFields([
      { key: "title", label: "Title", type: "text" },
      { key: 1, label: "x", type: "toggle" },
      { key: "x", type: "toggle" },
      { key: "y", label: "Y" },
      null, "toggle", [],
      { key: "ok", label: "Ok", type: "toggle" },
    ])).toEqual([{ key: "ok", label: "Ok", type: "toggle" }]);
  });
  it("filters select options and skips a select left with none", () => {
    expect(readOptionFields([
      { key: "a", label: "A", type: "select", options: [{ value: "x", label: "X" }, { value: 1, label: "One" }, { value: "y" }, null] },
      { key: "b", label: "B", type: "select", options: [{ value: 2, label: "Two" }] },
      { key: "c", label: "C", type: "select" },
    ])).toEqual([{ key: "a", label: "A", type: "select", options: [{ value: "x", label: "X" }] }]);
  });
  it("keeps default only when its type fits", () => {
    const opts = [{ value: "x", label: "X" }];
    expect(readOptionFields([
      { key: "t1", label: "T", type: "toggle", default: "true" },
      { key: "t2", label: "T", type: "toggle", default: false },
      { key: "s1", label: "S", type: "select", options: opts, default: true },
      { key: "s2", label: "S", type: "select", options: opts, default: "x" },
      { key: "c1", label: "C", type: "color", default: 0 },
      { key: "c2", label: "C", type: "color", default: "#112233" },
    ]).map((f) => f.default)).toEqual([undefined, false, undefined, "x", undefined, "#112233"]);
  });
  it("drops extra properties", () => {
    expect(readOptionFields([{ key: "a", label: "A", type: "toggle", hint: "h", style: "x" }])).toEqual(
      [{ key: "a", label: "A", type: "toggle" }]);
  });
});

describe("readOptions", () => {
  it("returns stored values that are valid", () => {
    expect(readOptions(svc({ show_title: false, content_width: "wide", background: "#f5f0e8" }), defaults)).toEqual(
      { show_title: false, content_width: "wide", background: "#f5f0e8" });
  });
  it("returns all defaults for a missing or malformed service", () => {
    for (const raw of [undefined, null, "x", [], {}, { _schema: schema }, { values: { show_title: false } },
      { _type: "options", values: { show_title: false } }, svc({ show_title: false }, null), svc({ show_title: false }, "nope"), { _schema: schema, values: [] }]) {
      expect(readOptions(raw, defaults)).toEqual(defaults);
    }
  });
  it("has exactly the keys of defaults; unknown stored keys are ignored", () => {
    const r = readOptions(svc({ show_title: false, extra: "x", __proto__: { polluted: true } }), { show_title: true });
    expect(r).toEqual({ show_title: false });
    expect(Object.keys(r)).toEqual(["show_title"]);
  });
  it("uses the default for a key the schema does not declare", () => {
    const s = [{ key: "show_title", label: "Show title", type: "toggle" }];
    expect(readOptions(svc({ show_title: false, content_width: "wide" }, s), defaults)).toEqual(
      { ...defaults, show_title: false });
  });
  it("uses the default for a key with no stored value", () => {
    expect(readOptions(svc({}), { show_title: false, content_width: "wide", background: "#000000" })).toEqual(
      { show_title: false, content_width: "wide", background: "#000000" });
  });
  it("toggle: only a real boolean", () => {
    for (const v of ["false", 0, null, ""]) expect(readOptions(svc({ show_title: v }), defaults).show_title).toBe(true);
  });
  it("select: only a declared option; \"\" means not chosen", () => {
    for (const v of ["huge", "", "WIDE", 1, true, null]) {
      expect(readOptions(svc({ content_width: v }), defaults).content_width).toBe("normal");
    }
    const s = [{ key: "content_width", label: "W", type: "select", options: [{ value: "", label: "None" }, { value: "wide", label: "Wide" }] }];
    expect(readOptions(svc({ content_width: "" }, s), { content_width: "normal" }).content_width).toBe("normal");
  });
  it("color: \"\" or a hex, lowercased", () => {
    expect(readOptions(svc({ background: "#ABCDEF" }), defaults).background).toBe("#abcdef");
    expect(readOptions(svc({ background: "" }), { ...defaults, background: "#ffffff" }).background).toBe("");
    for (const v of ["#fff", "red", "#abcdef;color:red", "url(x)", 0, false]) {
      expect(readOptions(svc({ background: v }), { ...defaults, background: "#ffffff" }).background).toBe("#ffffff");
    }
  });
  it("ignores a value when the schema type does not match the default's type", () => {
    // schema says toggle, site default is a string
    expect(readOptions(svc({ show_title: false }), { show_title: "yes" })).toEqual({ show_title: "yes" });
    // schema says select / color, site default is a boolean
    expect(readOptions(svc({ content_width: "wide", background: "#000000" }), { content_width: true, background: false })).toEqual(
      { content_width: true, background: false });
    // stored value has the default's type but not the schema's
    const s = [{ key: "flag", label: "F", type: "color" }];
    expect(readOptions(svc({ flag: true }, s), { flag: false })).toEqual({ flag: false });
  });
  it("does not consult the schema's own default", () => {
    const s = [{ key: "show_title", label: "Show title", type: "toggle", default: false }];
    expect(readOptions(svc({}, s), { show_title: true })).toEqual({ show_title: true });
  });
  it("skips a select whose options are all malformed", () => {
    const s = [{ key: "content_width", label: "W", type: "select", options: [{ value: 1, label: "x" }] }];
    expect(readOptions(svc({ content_width: "wide" }, s), defaults).content_width).toBe("normal");
  });
  it("returns a new object and leaves defaults alone", () => {
    const d = { ...defaults };
    const r = readOptions(svc({ show_title: false }), d);
    expect(r).not.toBe(d);
    expect(d).toEqual(defaults);
    expect(readOptions(undefined, d)).not.toBe(d);
  });
  it("ignores inherited properties of values", () => {
    const s = [{ key: "toString", label: "T", type: "toggle" }];
    expect(readOptions(svc({}, s), { toString: true })).toEqual({ toString: true });
  });
});

describe("inkOn", () => {
  it("dark ink on a light background, light ink on a dark one", () => {
    expect(inkOn("#ffffff")).toBe("#111827");
    expect(inkOn("#f5f0e8")).toBe("#111827");
    expect(inkOn("#000000")).toBe("#ffffff");
    expect(inkOn("#1e3a5f")).toBe("#ffffff");
  });
  it("uses the given colours", () => {
    expect(inkOn("#000000", "#222222", "#fafafa")).toBe("#fafafa");
    expect(inkOn("#ffffff", "#222222", "#fafafa")).toBe("#222222");
  });
  it("returns dark for an invalid background", () => {
    for (const v of ["", "#fff", "red", "#gggggg"]) expect(inkOn(v)).toBe("#111827");
    expect(inkOn("nope", "#333333")).toBe("#333333");
  });
  it("never picks an invalid ink", () => {
    expect(inkOn("#ffffff", "#111827", "white")).toBe("#111827");
    expect(inkOn("#ffffff", "black", "#ffffff")).toBe("#ffffff");
  });
});
