import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RepeaterEditor } from "../RepeaterEditor";

vi.mock("@/components/dashboard/rich-text/RichTextEditor", () => ({
  RichTextEditor: ({ value, label }: { value: string; label: string }) => {
    const [held] = useState(value); // uncontrolled, like TipTap
    return (
      <div data-testid="rte" aria-label={label}>
        {held}
      </div>
    );
  },
}));

const content = {
  _schema: [{ key: "body", label: "Body", type: "richtext" }],
  items: [{ body: "<p>first</p>" }, { body: "<p>second</p>" }],
};

describe("RepeaterEditor rich fields", () => {
  it("formatted text moves with its item", async () => {
    render(<RepeaterEditor initialContent={content} onChange={() => {}} richText />);
    await userEvent.click(screen.getAllByRole("button", { name: "Move down" })[0]);
    expect(screen.getAllByTestId("rte").map((n) => n.textContent)).toEqual([
      "<p>second</p>",
      "<p>first</p>",
    ]);
  });
  it("removing an item removes its text, not the last one", async () => {
    render(<RepeaterEditor initialContent={content} onChange={() => {}} richText />);
    await userEvent.click(screen.getAllByRole("button", { name: "Remove item" })[0]);
    expect(screen.getAllByTestId("rte").map((n) => n.textContent)).toEqual(["<p>second</p>"]);
  });
  it("emits items without internal keys", async () => {
    const onChange = vi.fn();
    render(<RepeaterEditor initialContent={content} onChange={onChange} richText />);
    await userEvent.click(screen.getAllByRole("button", { name: "Move down" })[0]);
    expect(onChange).toHaveBeenLastCalledWith({
      _schema: content._schema,
      items: [{ body: "<p>second</p>" }, { body: "<p>first</p>" }],
    });
  });
});

describe("RepeaterEditor slug fields", () => {
  const slugSchema = [{ key: "slug", type: "slug", label: "Slug" }];

  it.each([false, true])(
    "renders a plain input that slugifies on blur (richText=%s)",
    async (richText) => {
      const onChange = vi.fn();
      render(
        <RepeaterEditor
          initialContent={{ _schema: slugSchema, items: [{ slug: "" }] }}
          onChange={onChange}
          richText={richText}
        />
      );
      expect(screen.queryByTestId("rte")).not.toBeInTheDocument();
      expect(screen.getByText("URL part — letters, numbers and hyphens")).toBeInTheDocument();
      const input = screen.getByRole("textbox");
      await userEvent.click(input);
      await userEvent.paste("Reparații Laptop & PC");
      expect(onChange).toHaveBeenLastCalledWith({
        _schema: slugSchema,
        items: [{ slug: "Reparații Laptop & PC" }],
      });
      await userEvent.tab();
      expect(onChange).toHaveBeenLastCalledWith({
        _schema: slugSchema,
        items: [{ slug: "reparatii-laptop-pc" }],
      });
      expect(input).toHaveValue("reparatii-laptop-pc");
    }
  );

  it("does not emit on blur when the value is already a slug", async () => {
    const onChange = vi.fn();
    render(
      <RepeaterEditor
        initialContent={{ _schema: slugSchema, items: [{ slug: "laptop-repairs" }] }}
        onChange={onChange}
      />
    );
    await userEvent.click(screen.getByRole("textbox"));
    await userEvent.tab();
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe("RepeaterEditor media fields", () => {
  const imageSchema = [
    { key: "banner", type: "image", label: "Banner", hint: { width: 1600, height: 600 } },
  ];

  it("uploads an image field's file and emits its URL", async () => {
    const onChange = vi.fn();
    const onUpload = vi.fn().mockResolvedValue("https://cdn.example.com/banner.jpg");
    const { container } = render(
      <RepeaterEditor
        initialContent={{ _schema: imageSchema, items: [{ banner: "" }] }}
        onChange={onChange}
        onUpload={onUpload}
        richText
      />
    );
    expect(screen.getByText(/1600 × 600 px \(landscape 8:3\)/)).toBeInTheDocument();
    const file = new File(["x"], "banner.jpg", { type: "image/jpeg" });
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')!;
    await userEvent.upload(input, file);
    expect(onUpload).toHaveBeenCalledWith(file);
    await waitFor(() =>
      expect(onChange).toHaveBeenLastCalledWith({
        _schema: imageSchema,
        items: [{ banner: "https://cdn.example.com/banner.jpg" }],
      })
    );
  });

  it("renders an icon field with the icon controls", () => {
    render(
      <RepeaterEditor
        initialContent={{
          _schema: [{ key: "icon", type: "icon", label: "Icon", surface: "Page" }],
          items: [{ icon: null }],
        }}
        onChange={() => {}}
        richText
      />
    );
    expect(screen.getByRole("button", { name: "Choose icon" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload SVG/PNG" })).toBeInTheDocument();
  });

  it("adds items with an empty image and no icon", async () => {
    const onChange = vi.fn();
    const schema = [
      { key: "banner", type: "image", label: "Banner" },
      { key: "icon", type: "icon", label: "Icon" },
    ];
    render(<RepeaterEditor initialContent={{ _schema: schema, items: [] }} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Add item" }));
    expect(onChange).toHaveBeenLastCalledWith({
      _schema: schema,
      items: [{ banner: "", icon: null }],
    });
  });
});

describe("RepeaterEditor option fields", () => {
  const optionSchema = [
    { key: "show_title", label: "Show title", type: "toggle" },
    {
      key: "layout",
      label: "Layout",
      type: "select",
      options: [
        { value: "image_left", label: "Image left" },
        { value: "image_top", label: "Image top" },
      ],
    },
    { key: "accent", label: "Accent", type: "color" },
  ];

  it("renders toggle, select and colour fields and updates the item", async () => {
    const onChange = vi.fn();
    render(
      <RepeaterEditor
        initialContent={{
          _schema: optionSchema,
          items: [{ show_title: true, layout: "image_left", accent: "#112233" }],
        }}
        onChange={onChange}
        richText
      />
    );
    expect(screen.queryByTestId("rte")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("switch", { name: "Show title" }));
    expect(onChange).toHaveBeenLastCalledWith({
      _schema: optionSchema,
      items: [{ show_title: false, layout: "image_left", accent: "#112233" }],
    });
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Layout" }), "image_top");
    expect(onChange).toHaveBeenLastCalledWith({
      _schema: optionSchema,
      items: [{ show_title: false, layout: "image_top", accent: "#112233" }],
    });
    await userEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(onChange).toHaveBeenLastCalledWith({
      _schema: optionSchema,
      items: [{ show_title: false, layout: "image_top", accent: "" }],
    });
  });

  it("shows defaults for an older item that lacks the keys, without emitting", () => {
    const onChange = vi.fn();
    const schema = [
      { ...optionSchema[0], default: true },
      { ...optionSchema[1], default: "image_top" },
      optionSchema[2],
    ];
    render(
      <RepeaterEditor initialContent={{ _schema: schema, items: [{}] }} onChange={onChange} />
    );
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("combobox")).toHaveValue("image_top");
    expect(screen.getByLabelText("Accent hex")).toHaveValue("");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("seeds new items with each field's default", async () => {
    const onChange = vi.fn();
    const schema = [
      ...optionSchema,
      { key: "show_cta", label: "Show CTA", type: "toggle", default: true },
      { ...optionSchema[1], key: "variant", default: "image_top" },
      { key: "bg", label: "Background", type: "color", default: "#ABC" },
    ];
    render(<RepeaterEditor initialContent={{ _schema: schema, items: [] }} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Add item" }));
    expect(onChange).toHaveBeenLastCalledWith({
      _schema: schema,
      items: [
        {
          show_title: false,
          layout: "",
          accent: "",
          show_cta: true,
          variant: "image_top",
          bg: "#aabbcc",
        },
      ],
    });
  });
});
