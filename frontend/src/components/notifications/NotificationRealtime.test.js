/**
 * @jest-environment jsdom
 */
import { render, waitFor } from "@testing-library/react";
import NotificationRealtime from "./NotificationRealtime";

const mockShowAlert = jest.fn();
const mockOnIncoming = jest.fn();
let mockPushCb = null;

jest.mock("../../context/AlertContext", () => ({
    useAlertContext: () => ({ showAlert: mockShowAlert }),
}));

jest.mock("../../services/notificationsApi", () => ({
    subscribeNotifications: (cb) => {
        mockPushCb = cb;
        return () => {
            mockPushCb = null;
        };
    },
}));

describe("NotificationRealtime", () => {
    beforeEach(() => {
        mockShowAlert.mockClear();
        mockOnIncoming.mockClear();
        mockPushCb = null;
    });

    it("toasts and notifies parent on incoming payload", async () => {
        render(<NotificationRealtime enabled userId="42" onIncoming={mockOnIncoming} />);

        await waitFor(() => expect(typeof mockPushCb).toBe("function"));
        mockPushCb({
            type: "notification",
            content: "Новый отклик",
            id: 1,
            user_id: "42",
            entity_type: "candidate",
            entity_id: 5,
        });

        expect(mockShowAlert).toHaveBeenCalledWith("Новый отклик", "info");
        expect(mockOnIncoming).toHaveBeenCalled();
    });

    it("ignores non-notification payloads", async () => {
        render(<NotificationRealtime enabled userId="42" onIncoming={mockOnIncoming} />);
        await waitFor(() => expect(typeof mockPushCb).toBe("function"));
        mockPushCb({ type: "other", content: "x" });
        expect(mockShowAlert).not.toHaveBeenCalled();
    });

    it("accepts a matching role notification and ignores another role", async () => {
        render(<NotificationRealtime enabled userId="42" roleId={2} onIncoming={mockOnIncoming} />);
        await waitFor(() => expect(typeof mockPushCb).toBe("function"));
        mockPushCb({ type: "notification", content: "Role msg", role_id: 2 });
        expect(mockShowAlert).toHaveBeenCalledWith("Role msg", "info");
        expect(mockOnIncoming).toHaveBeenCalledTimes(1);

        mockPushCb({ type: "notification", content: "Other role", role_id: 4 });
        expect(mockShowAlert).toHaveBeenCalledTimes(1);
        expect(mockOnIncoming).toHaveBeenCalledTimes(1);
    });
});
