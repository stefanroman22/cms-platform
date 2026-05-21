import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EditingSectionProvider } from "../../context/EditingSectionContext";
import { EditableSectionShell } from "../EditableSectionShell";

function setup(props: Partial<React.ComponentProps<typeof EditableSectionShell>> = {}) {
  const onSave = vi.fn().mockResolvedValue(undefined);
  const onCancel = vi.fn();
  render(
    <EditingSectionProvider>
      <EditableSectionShell
        id="test"
        title="Test"
        readView={<div>READ</div>}
        editView={<div>EDIT</div>}
        onSave={onSave}
        onCancel={onCancel}
        saving={false}
        error={null}
        canSave
        {...props}
      />
    </EditingSectionProvider>
  );
  return { onSave, onCancel };
}

describe("EditableSectionShell", () => {
  it("shows the read view by default", () => {
    setup();
    expect(screen.getByText("READ")).toBeTruthy();
    expect(screen.queryByText("EDIT")).toBeNull();
  });

  it("reveals the edit view when the pencil is clicked", () => {
    setup();
    fireEvent.click(screen.getByLabelText("Edit Test"));
    expect(screen.getByText("EDIT")).toBeTruthy();
  });

  it("calls onSave when Save is clicked", () => {
    const { onSave } = setup();
    fireEvent.click(screen.getByLabelText("Edit Test"));
    fireEvent.click(screen.getByText("Save"));
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel and returns to read view when Cancel is clicked", () => {
    const { onCancel } = setup();
    fireEvent.click(screen.getByLabelText("Edit Test"));
    fireEvent.click(screen.getByText("Cancel"));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(screen.getByText("READ")).toBeTruthy();
  });

  it("disables Save when canSave is false", () => {
    setup({ canSave: false });
    fireEvent.click(screen.getByLabelText("Edit Test"));
    const saveBtn = screen.getByText("Save").closest("button")!;
    expect(saveBtn.hasAttribute("disabled")).toBe(true);
  });
});
