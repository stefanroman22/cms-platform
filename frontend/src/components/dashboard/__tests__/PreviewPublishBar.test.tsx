import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PreviewPublishBar } from "../PreviewPublishBar";

const mockStatus = (body: Record<string, unknown>) => ({
    ok: true,
    json: async () => body,
});

beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    global.fetch = vi.fn();
});

afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
});

describe("PreviewPublishBar", () => {
    it("disables See Preview when preview_url is null", async () => {
        (global.fetch as any).mockResolvedValueOnce(
            mockStatus({ unpublished_count: 0, last_published_at: null, preview_url: null, production_url: null }),
        );

        render(<PreviewPublishBar projectSlug="demo" projectName="Demo" />);

        await waitFor(() => {
            expect(screen.getByRole("button", { name: /See Preview/i })).toBeDisabled();
        });
    });

    it("disables Publish Changes when unpublished_count is 0", async () => {
        (global.fetch as any).mockResolvedValueOnce(
            mockStatus({
                unpublished_count: 0,
                last_published_at: "2026-04-15T10:00:00Z",
                preview_url: "https://preview.example.com",
                production_url: "https://prod.example.com",
            }),
        );

        render(<PreviewPublishBar projectSlug="demo" projectName="Demo" />);

        await waitFor(() => {
            expect(screen.getByRole("button", { name: /Publish Changes/i })).toBeDisabled();
        });
    });

    it("shows 'N unpublished changes' badge when count > 0", async () => {
        (global.fetch as any).mockResolvedValueOnce(
            mockStatus({
                unpublished_count: 3,
                last_published_at: null,
                preview_url: "https://preview.example.com",
                production_url: "https://prod.example.com",
            }),
        );

        render(<PreviewPublishBar projectSlug="demo" projectName="Demo" />);

        expect(await screen.findByText(/3 unpublished changes/i)).toBeInTheDocument();
    });

    it("opens modal on Publish click, confirms, calls /publish, refetches status", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

        (global.fetch as any)
            // Initial status
            .mockResolvedValueOnce(
                mockStatus({
                    unpublished_count: 2,
                    last_published_at: null,
                    preview_url: "https://preview.example.com",
                    production_url: "https://prod.example.com",
                }),
            )
            // Publish POST
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ published_count: 2, last_published_at: "2026-04-16T12:00:00Z" }),
            })
            // Status refetch after publish
            .mockResolvedValueOnce(
                mockStatus({
                    unpublished_count: 0,
                    last_published_at: "2026-04-16T12:00:00Z",
                    preview_url: "https://preview.example.com",
                    production_url: "https://prod.example.com",
                }),
            );

        render(<PreviewPublishBar projectSlug="demo" projectName="Demo" />);

        const publishBtn = await screen.findByRole("button", { name: /Publish Changes/i });
        await user.click(publishBtn);

        // Modal opens
        const confirmBtn = await screen.findByRole("button", { name: /^Publish$/i });
        await user.click(confirmBtn);

        await waitFor(() => {
            const publishCall = (global.fetch as any).mock.calls.find(
                (c: any[]) => typeof c[0] === "string" && c[0].includes("/publish"),
            );
            expect(publishCall).toBeTruthy();
            expect(publishCall[1].method).toBe("POST");
        });

        // After refetch, badge disappears
        await waitFor(() => {
            expect(screen.queryByText(/unpublished changes/i)).not.toBeInTheDocument();
        });
    });
});
