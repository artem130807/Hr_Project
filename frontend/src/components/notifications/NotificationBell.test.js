import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

jest.mock(
    "react-router-dom",
    () => ({
        useNavigate: () => jest.fn(),
    }),
    { virtual: true }
);

jest.mock("../../context/AuthContext", () => ({
    useAuth: () => ({
        user: { id: 42, role: "hr", role_id: 7, name: "Тест HR" },
    }),
}));

jest.mock("../../context/AlertContext", () => ({
    useAlertContext: () => ({ showAlert: jest.fn() }),
}));

import NotificationBell from "./NotificationBell";
import { __resetNotificationsMock } from "../../services/notificationsMock";

describe("NotificationBell", () => {
    beforeEach(() => {
        __resetNotificationsMock({
            messages: [
                {
                    id: 1,
                    content: "Личное сообщение",
                    is_read: false,
                    user_id: "42",
                    role: null,
                    channel_id: null,
                    entity_type: "vacancy",
                    entity_id: 1,
                    created_at: new Date().toISOString(),
                },
            ],
            channels: [],
            settings: [],
            nextId: 2,
            nextSettingId: 1,
        });
    });

    it("shows unread badge and opens personal list", async () => {
        render(<NotificationBell />);

        await waitFor(() => {
            expect(screen.getByText("1")).toBeInTheDocument();
        });

        fireEvent.click(screen.getByLabelText(/Уведомления/i));
        expect(screen.getAllByText("Уведомления").length).toBeGreaterThan(0);
        await waitFor(() => {
            expect(screen.getByText("Личное сообщение")).toBeInTheDocument();
        });
    });

    it("loads role notifications together with personal notifications", async () => {
        __resetNotificationsMock({
            messages: [{
                id: 5,
                content: "Создана заявка на подбор",
                is_read: false,
                user_id: null,
                role: "hr",
                role_id: 7,
                channel_id: null,
                entity_type: "hiring_request",
                entity_id: 10,
                created_at: new Date().toISOString(),
            }],
            channels: [], settings: [], nextId: 6, nextSettingId: 1,
        });
        render(<NotificationBell />);
        fireEvent.click(screen.getByLabelText(/Уведомления/i));
        await waitFor(() => expect(screen.getByText("Создана заявка на подбор")).toBeInTheDocument());
    });
});
