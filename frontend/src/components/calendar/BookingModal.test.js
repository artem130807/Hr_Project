/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import BookingModal from "./BookingModal";

jest.mock("../../context/AlertContext", () => ({
    useAlertContext: () => ({ showAlert: jest.fn() }),
}));

jest.mock("../../context/AuthContext", () => ({
    useAuth: () => ({ user: { name: "HR", erp_user_id: "hr-1" } }),
}));

jest.mock("../../services/sheduleApi", () => ({
    bookSlot: jest.fn(),
}));

jest.mock("../../services/eventsApi", () => ({
    createEvent: jest.fn(),
    searchEventEmployees: jest.fn(),
}));

jest.mock("../../services/candidateApi", () => ({
    getCandidates: jest.fn(),
    getCandidate: jest.fn(),
    sendInterviewInvite: jest.fn(),
    loadCandidateVacancyTitle: jest.fn(),
}));

const { bookSlot } = require("../../services/sheduleApi");
const { createEvent, searchEventEmployees } = require("../../services/eventsApi");
const { getCandidates, getCandidate, sendInterviewInvite, loadCandidateVacancyTitle } = require("../../services/candidateApi");

describe("BookingModal interview reminder flow", () => {
    beforeEach(() => {
        bookSlot.mockReset();
        createEvent.mockReset();
        searchEventEmployees.mockReset();
        getCandidates.mockReset();
        loadCandidateVacancyTitle.mockReset();
        getCandidate.mockReset();
        sendInterviewInvite.mockReset();
        sendInterviewInvite.mockResolvedValue({ status: "ok", delivery: "sent" });
        getCandidates.mockResolvedValue({
            items: [{ id: 5, full_name: "Иван Иванов", telegram_username: "@ivan_hr" }],
        });
        getCandidate.mockResolvedValue({
            id: 5,
            full_name: "Иван Иванов",
            telegram_username: "@ivan567",
            email: "ivan@example.com",
            phone_number: "+79990000000",
        });
        loadCandidateVacancyTitle.mockResolvedValue("Логист");
        searchEventEmployees.mockResolvedValue([
            { erp_user_id: "u1", full_name: "HR Петров", tg_username: "@hr_petrov" },
        ]);
        bookSlot.mockResolvedValue({ status: "ok" });
        createEvent.mockResolvedValue({ id: 1 });
        window.confirm = jest.fn((question) => {
            const q = String(question || "");
            if (q.includes("hh.ru")) return false;
            return true;
        });
    });

    test("opens and saves prefilled interview reminder after booking", async () => {
        const onClose = jest.fn();
        const onSuccess = jest.fn();
        render(
            <BookingModal
                slot={{ id: 9, date: "2026-08-21", start_time: "10:00:00", end_time: "11:00:00" }}
                onClose={onClose}
                onSuccess={onSuccess}
            />
        );

        const select = await screen.findByTestId("booking-candidate-select");
        fireEvent.change(select, { target: { value: "5" } });
        fireEvent.click(screen.getByText("Забронировать"));

        await screen.findByTestId("interview-reminder-form");
        expect(screen.getByDisplayValue("Иван Иванов")).toBeInTheDocument();
        expect(screen.getByDisplayValue("Логист")).toBeInTheDocument();
        expect(screen.getByDisplayValue(/Контакты кандидата/i)).toBeInTheDocument();

        fireEvent.change(screen.getByPlaceholderText("Начните вводить ФИО сотрудника"), {
            target: { value: "HR Петров" },
        });
        await waitFor(() => expect(searchEventEmployees).toHaveBeenCalled());
        fireEvent.click(await screen.findByText("HR Петров"));

        fireEvent.click(screen.getByText("Сохранить напоминание"));

        await waitFor(() => expect(createEvent).toHaveBeenCalled());
        expect(createEvent.mock.calls[0][0]).toEqual(
            expect.objectContaining({
                type: "interview",
                employee_name: null,
                event_date: "2026-08-21",
                telegram_user: "@hr_petrov",
            })
        );
        expect(createEvent.mock.calls[0][0].note).toContain("Логист");
        expect(createEvent.mock.calls[0][0].note).toContain("ivan@example.com");
        expect(createEvent.mock.calls[0][0].note).toContain("+79990000000");
        expect(onSuccess).toHaveBeenCalled();
        expect(onClose).toHaveBeenCalled();
    });
});
