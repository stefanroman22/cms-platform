import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PublishConfirmModal } from "../PublishConfirmModal";

describe("PublishConfirmModal", () => {
    it("is hidden when open=false", () => {
        render(
            <PublishConfirmModal
                open={false}
                count={3}
                projectName="Laurian Portfolio"
                onCancel={() => {}}
                onConfirm={() => {}}
            />
        );
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("shows count and project name when open", () => {
        render(
            <PublishConfirmModal
                open
                count={3}
                projectName="Laurian Portfolio"
                onCancel={() => {}}
                onConfirm={() => {}}
            />
        );
        expect(screen.getByText(/3 changes/i)).toBeInTheDocument();
        expect(screen.getByText(/Laurian Portfolio/i)).toBeInTheDocument();
    });

    it("calls onCancel when Cancel is clicked", async () => {
        const user = userEvent.setup();
        const onCancel = vi.fn();
        render(
            <PublishConfirmModal open count={1} projectName="X" onCancel={onCancel} onConfirm={() => {}} />
        );
        await user.click(screen.getByRole("button", { name: /Cancel/i }));
        expect(onCancel).toHaveBeenCalledOnce();
    });

    it("calls onConfirm when Publish is clicked", async () => {
        const user = userEvent.setup();
        const onConfirm = vi.fn();
        render(
            <PublishConfirmModal open count={1} projectName="X" onCancel={() => {}} onConfirm={onConfirm} />
        );
        await user.click(screen.getByRole("button", { name: /^Publish$/i }));
        expect(onConfirm).toHaveBeenCalledOnce();
    });
});
