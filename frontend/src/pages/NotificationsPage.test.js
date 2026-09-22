import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TextEncoder, TextDecoder } from "util";

global.TextEncoder = TextEncoder;
global.TextDecoder = TextDecoder;

const mockNavigate = jest.fn();
let mockSection = "";

jest.mock("react-router-dom", () => ({
    useNavigate: () => mockNavigate,
    useSearchParams: () => [new URLSearchParams(mockSection), jest.fn()],
}), { virtual: true });

const mockShowAlert = jest.fn();
const mockApi = {
    fetchMessages: jest.fn(),
    fetchUnreadCount: jest.fn(),
    fetchUserChannels: jest.fn(),
    fetchUserSettings: jest.fn(),
    markMessageAsRead: jest.fn(),
    markMessagesAsRead: jest.fn(),
    createChannelSettings: jest.fn(),
    updateChannelSettings: jest.fn(),
};

jest.mock("../layout/MainLayout", () => ({ children }) => <div>{children}</div>);
jest.mock("../context/AuthContext", () => ({
    useAuth: () => ({ user: { id: "user-1", role: "hr", role_id: 3 } }),
}));
jest.mock("../context/AlertContext", () => ({
    useAlertContext: () => ({ showAlert: mockShowAlert }),
}));
jest.mock("../services/notificationsApi", () => mockApi);

const NotificationsPage = require("./NotificationsPage").default;

describe("NotificationsPage", () => {
    beforeEach(() => {
        jest.clearAllMocks();
        mockSection = "";
        mockApi.fetchUnreadCount.mockResolvedValue(1);
        mockApi.fetchMessages.mockResolvedValue([
            {
                id: 7,
                content: "Новая заявка на подбор",
                is_read: false,
                entity_type: "hiring_request",
                entity_id: 12,
                created_at: new Date().toISOString(),
            },
        ]);
        mockApi.fetchUserChannels.mockResolvedValue([]);
        mockApi.fetchUserSettings.mockResolvedValue([]);
        mockApi.markMessageAsRead.mockResolvedValue({ id: 7, is_read: true });
        mockApi.markMessagesAsRead.mockResolvedValue(1);
    });

    it("loads personal notifications and marks one on click", async () => {
        render(<NotificationsPage />);

        expect(screen.getByRole("heading", { name: "Уведомления" })).toBeTruthy();
        expect(await screen.findByText("Новая заявка на подбор")).toBeTruthy();
        expect(mockApi.fetchMessages).toHaveBeenCalledWith(
            { user_id: "user-1" },
            expect.objectContaining({ signal: expect.any(AbortSignal) })
        );

        fireEvent.click(screen.getByLabelText(/Новая заявка на подбор, непрочитано/));
        await waitFor(() => expect(mockApi.markMessageAsRead).toHaveBeenCalledWith(7));
    });

    it("loads channels from the channels tab", async () => {
        mockApi.fetchUserChannels.mockResolvedValue([{ id: 1, name: "Заявки", unread_count: 2 }]);
        mockSection = "section=channels";
        render(<NotificationsPage />);

        expect(await screen.findByText("Заявки")).toBeTruthy();
        expect(mockApi.fetchUserChannels).toHaveBeenCalled();
        expect(mockApi.fetchUserSettings).toHaveBeenCalled();
    });
});
