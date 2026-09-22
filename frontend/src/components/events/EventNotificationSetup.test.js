/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import EventNotificationSetup from "./EventNotificationSetup";

jest.mock("../../context/AlertContext", () => ({
    useAlertContext: () => ({ showAlert: jest.fn() }),
}));

jest.mock("../../context/AuthContext", () => ({
    useAuth: () => ({ user: { name: "HR", erp_user_id: "hr-1" } }),
}));

jest.mock("../../services/eventsApi", () => ({
    createEvent: jest.fn(),
    searchEventEmployees: jest.fn(),
}));

jest.mock("../../services/candidateApi", () => ({
    getCandidates: jest.fn(),
    sendInterviewInvite: jest.fn(),
}));

const { createEvent, searchEventEmployees } = require("../../services/eventsApi");
const { getCandidates, sendInterviewInvite } = require("../../services/candidateApi");

describe("EventNotificationSetup interview HH invite", () => {
    beforeEach(() => {
        createEvent.mockReset();
        searchEventEmployees.mockReset();
        getCandidates.mockReset();
        sendInterviewInvite.mockReset();
        createEvent.mockResolvedValue({ id: 1 });
        searchEventEmployees.mockResolvedValue([
            { erp_user_id: "u1", full_name: "HR Петров", tg_username: "@hr_petrov" },
        ]);
        getCandidates.mockResolvedValue({
            items: [{ id: 5, full_name: "Иванов Артём Валерьевич" }],
        });
        sendInterviewInvite.mockResolvedValue({ status: "ok", delivery: "sent" });
        window.confirm = jest.fn(() => true);
    });

    it("asks to send hh.ru interview letter after creating interview event", async () => {
        render(<EventNotificationSetup onRefresh={jest.fn()} />);
        fireEvent.change(screen.getByRole("combobox"), { target: { value: "interview" } });
        await waitFor(() => expect(getCandidates).toHaveBeenCalled());
        fireEvent.change(await screen.findByTestId("event-candidate-select"), { target: { value: "5" } });
        const dateInput = screen.getByText("Дата").parentElement.querySelector("input");
        fireEvent.change(dateInput, { target: { value: "2026-07-09" } });
        const timeInput = screen.getByText("Время собеседования").parentElement.querySelector("input");
        fireEvent.change(timeInput, { target: { value: "16:00" } });
        fireEvent.change(screen.getByPlaceholderText("Выберите сотрудника из ERP"), {
            target: { value: "HR Петров" },
        });
        await waitFor(() => expect(searchEventEmployees).toHaveBeenCalled());
        fireEvent.click(await screen.findByText("HR Петров"));
        fireEvent.click(screen.getByRole("button", { name: /Добавить/i }));
        await waitFor(() => expect(createEvent).toHaveBeenCalled());
        expect(window.confirm).toHaveBeenCalledWith(
            "Отправить кандидату сообщение о собеседовании на hh.ru?"
        );
        expect(await screen.findByText("Пригласить на собеседование")).toBeInTheDocument();
    });
});
