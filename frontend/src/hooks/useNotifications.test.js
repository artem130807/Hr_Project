/**
 * @jest-environment jsdom
 */
import { renderHook, act, waitFor } from "@testing-library/react";
import { useNotifications } from "./useNotifications";

jest.mock("../services/notificationsApi", () => ({
    fetchUnreadCount: jest.fn(),
    fetchMessages: jest.fn(),
    markMessagesAsRead: jest.fn(),
}));

const api = require("../services/notificationsApi");

describe("useNotifications", () => {
    const user = { id: 42, role: "hr", name: "HR" };

    beforeEach(() => {
        jest.clearAllMocks();
        api.fetchUnreadCount.mockResolvedValue(3);
        api.fetchMessages.mockResolvedValue([
            { id: 1, content: "Hi", is_read: false, created_at: new Date().toISOString() },
        ]);
        api.markMessagesAsRead.mockResolvedValue(1);
    });

    it("loads unread badge on mount", async () => {
        const { result } = renderHook(() => useNotifications({ user, enabled: true }));
        await waitFor(() => expect(result.current.unreadCount).toBe(3));
        expect(result.current.badgeText).toBe("3");
    });

    it("opens personal list and marks read", async () => {
        const { result } = renderHook(() => useNotifications({ user, enabled: true }));
        await waitFor(() => expect(result.current.unreadCount).toBe(3));

        act(() => {
            result.current.togglePanel();
        });

        await waitFor(() => {
            expect(api.markMessagesAsRead).toHaveBeenCalledWith(
                { user_id: "42" },
                expect.any(Object)
            );
            expect(result.current.messages).toHaveLength(1);
            expect(result.current.messages[0].is_read).toBe(true);
        });
    });
});
