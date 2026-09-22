/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CallsPage from "./CallsPage";
import { getCallConversations } from "../services/callsApi";

jest.mock(
    "react-router-dom",
    () => ({
        NavLink: ({ children, to }) => <a href={to}>{children}</a>,
        useNavigate: () => jest.fn(),
    }),
    { virtual: true }
);

jest.mock("../context/AlertContext", () => ({
    useAlertContext: () => ({ showAlert: jest.fn() }),
}));

jest.mock("../context/AuthContext", () => ({
    useAuth: () => ({
        user: { id: 1, role: "hr", username: "hr" },
        logout: jest.fn(),
    }),
}));

jest.mock("../services/userApi", () => ({ getInviteUrl: jest.fn() }));
jest.mock("../services/hhAuthApi", () => ({
    checkHHAuth: jest.fn(() => Promise.resolve({ auth_passed: true })),
    getHHAuthLink: jest.fn(() => Promise.resolve("https://hh.example/auth")),
}));
jest.mock("../components/sidebar/AutoSelectSection", () => () => null);
jest.mock("../components/notifications/NotificationBell", () => () => null);
jest.mock("../services/callsApi", () => ({
    getCallConversations: jest.fn(),
}));
jest.mock("../services/t2AuthApi", () => ({
    getT2OAuthTokens: jest.fn(() => Promise.resolve({ payload: { access_token: "a", refresh_token: "r" } })),
    putT2OAuthTokens: jest.fn(),
    deleteT2OAuthTokens: jest.fn(),
    isT2AtsConnected: () => true,
}));

const API_CALLS = [
    {
        id: 1001,
        filename: "recording_smirnov.mp3",
        description: null,
        callStartTime: "2026-08-22T09:14:00+04:00",
        callerNumber: "+79020013728",
        operatorNumber: "+79007654321",
        duration: 312,
        status: "pending",
        direction: "outgoing",
        callerName: "Алексей Смирнов",
        turns: [
            { at: "00:04", speaker: "hr", text: "Алексей, добрый день" },
            { at: "00:18", speaker: "candidate", text: "Да, добрый" },
        ],
    },
    {
        id: 1002,
        filename: "recording_kozlova.mp3",
        description: "Перезвон: уточняла удалёнку.",
        callStartTime: "2026-08-22T11:40:00+04:00",
        callerNumber: "+79035517702",
        operatorNumber: "+7 902 001 37 28",
        duration: 187,
        status: "callback",
        direction: "incoming",
        callerName: "Марина Козлова",
        turns: [{ at: "00:03", speaker: "candidate", text: "Алло, это по вакансии" }],
    },
    {
        id: 1003,
        filename: "recording_other.mp3",
        description: "Чужой номер — не должен попасть в список.",
        callStartTime: "2026-08-22T12:00:00+04:00",
        callerNumber: "+79992140831",
        operatorNumber: "+79007654321",
        duration: 40,
        status: "rejected",
        direction: "incoming",
        callerName: "Чужой абонент",
        turns: [{ at: "00:01", speaker: "candidate", text: "не должен отображаться" }],
    },
];

describe("CallsPage", () => {
    beforeEach(() => {
        getCallConversations.mockResolvedValue(API_CALLS);
    });

    it("renders calls and a transcript from the API", async () => {
        render(<CallsPage />);
        expect(screen.getByRole("heading", { name: "Звонки" })).toBeInTheDocument();
        await waitFor(() => {
            expect(screen.getByTestId("call-transcript")).toHaveTextContent("HR");
        });
        expect(screen.getByTestId("call-transcript")).toHaveTextContent("Собеседник");
        expect(screen.getByTestId("calls-list")).toHaveTextContent("Алексей Смирнов");
        expect(screen.getByTestId("calls-list")).toHaveTextContent("Определяется");
        expect(screen.getByTestId("calls-list")).not.toHaveTextContent("Чужой абонент");
    });

    it("filters the list by a concrete phone number", async () => {
        render(<CallsPage />);
        await waitFor(() => {
            expect(screen.getByTestId("calls-list")).toHaveTextContent("Алексей Смирнов");
        });
        fireEvent.change(screen.getByTestId("calls-phone-search"), {
            target: { value: "89035517702" },
        });
        const list = screen.getByTestId("calls-list");
        expect(list).toHaveTextContent("Марина Козлова");
        expect(list).not.toHaveTextContent("Алексей Смирнов");
        expect(list).not.toHaveTextContent("Чужой абонент");
        expect(screen.getByTestId("call-detail-phone")).toHaveTextContent("+7 903 551-77-02");
    });

    it("shows an empty state when the API returns nothing", async () => {
        getCallConversations.mockResolvedValue([]);
        render(<CallsPage />);
        await waitFor(() => {
            expect(screen.getByTestId("calls-list")).toHaveTextContent("Нет записей");
        });
        expect(screen.getByText(/Выберите звонок/)).toBeInTheDocument();
    });

    it("shows an empty state when the mocked API fails", async () => {
        getCallConversations.mockRejectedValue(new Error("network down"));
        render(<CallsPage />);
        await waitFor(() => {
            expect(screen.getByTestId("calls-list")).toHaveTextContent("Нет записей");
        });
    });

    it("filters by HR outcome from mocked data", async () => {
        render(<CallsPage />);
        await waitFor(() => {
            expect(screen.getByTestId("calls-list")).toHaveTextContent("Марина Козлова");
        });
        fireEvent.change(screen.getByDisplayValue("Все итоги"), {
            target: { value: "callback" },
        });
        const list = screen.getByTestId("calls-list");
        expect(list).toHaveTextContent("Марина Козлова");
        expect(list).not.toHaveTextContent("Алексей Смирнов");
    });

    it("opens another transcript from the mocked list", async () => {
        render(<CallsPage />);
        await waitFor(() => {
            expect(screen.getByTestId("call-row-1002")).toBeInTheDocument();
        });
        fireEvent.click(screen.getByTestId("call-row-1002"));
        expect(screen.getByTestId("call-transcript")).toHaveTextContent("Алло, это по вакансии");
        expect(screen.getByTestId("call-detail-phone")).toHaveTextContent("+7 903 551-77-02");
    });
});
