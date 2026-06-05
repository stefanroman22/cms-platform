import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SectionRail } from "../SectionRail";
import { visibleSections } from "../sectionConfig";

describe("SectionRail", () => {
  it("renders every section it is given as a tab", () => {
    render(
      <SectionRail sections={visibleSections(true)} activeView="dashboard" onSelect={vi.fn()} />
    );
    expect(screen.getByRole("tab", { name: /Dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /CMS/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Auto-Fix/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Settings/i })).toBeInTheDocument();
  });

  it("does not render Settings when given the non-admin section list", () => {
    render(
      <SectionRail sections={visibleSections(false)} activeView="dashboard" onSelect={vi.fn()} />
    );
    expect(screen.queryByRole("tab", { name: /Settings/i })).not.toBeInTheDocument();
  });

  it("marks the active tab with aria-selected", () => {
    render(<SectionRail sections={visibleSections(true)} activeView="cms" onSelect={vi.fn()} />);
    expect(screen.getByRole("tab", { name: /CMS/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /Dashboard/i })).toHaveAttribute(
      "aria-selected",
      "false"
    );
  });

  it("calls onSelect with the section key on click", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(
      <SectionRail sections={visibleSections(true)} activeView="dashboard" onSelect={onSelect} />
    );
    await user.click(screen.getByRole("tab", { name: /Auto-Fix/i }));
    expect(onSelect).toHaveBeenCalledWith("autofix");
  });

  it("moves selection with arrow keys", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(
      <SectionRail sections={visibleSections(true)} activeView="dashboard" onSelect={onSelect} />
    );
    const active = screen.getByRole("tab", { name: /Dashboard/i });
    active.focus();
    await user.keyboard("{ArrowDown}");
    expect(onSelect).toHaveBeenCalledWith("cms");
  });

  it("wraps to the last section when arrowing up from the first", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(
      <SectionRail sections={visibleSections(true)} activeView="dashboard" onSelect={onSelect} />
    );
    screen.getByRole("tab", { name: /Dashboard/i }).focus();
    await user.keyboard("{ArrowUp}");
    expect(onSelect).toHaveBeenCalledWith("settings");
  });
});
