/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import InterviewReminderModal from "./InterviewReminderModal";

jest.mock("../../context/AlertContext", () => ({
    useAlertContext: () => ({ showAlert: jest.fn() }),
}));

jest.mock("../../services/candidateApi", () => ({
    getCandidate: jest.fn(),
    loadCandidateVacancyTitle: jest.fn(),
}));

jest.mock("../../services/eventsApi", () => ({
    createEvent: jest.fn(),
    searchEventEmployees: jest.fn(),
}));

const { getCandidate, loadCandidateVacancyTitle } = require("../../services/candidateApi");
const { createEvent, searchEventEmployees } = require("../../services/eventsApi");

describe("InterviewReminderModal", () => {
    beforeEach(() => {
        getCandidate.mockReset();
        loadCandidateVacancyTitle.mockReset();
        createEvent.mockReset();
        searchEventEmployees.mockReset();
        getCandidate.mockResolvedValue({
            id: 5,
            full_name: "Иван Иванов",
            email: "ivan@example.com",
            phone_number: "+79990000000",
            telegram_username: "@ivan567",
        });
        loadCandidateVacancyTitle.mockResolvedValue("Логист");
        createEvent.mockResolvedValue({ id: 1 });
        searchEventEmployees.mockResolvedValue([
            { erp_user_id: "u1", full_name: "HR Петров", tg_username: "@hr_petrov" },
        ]);
    });

    test("prefills candidate vacancy and schedule then saves HR mention", async () => {
        const onSaved = jest.fn();
        render(
            <InterviewReminderModal
                open
                candidate={{ id: 5, full_name: "Иван Иванов" }}
                date="2026-08-21"
                startTime="10:00"
                endTime="11:00"
                onClose={jest.fn()}
                onSaved={onSaved}
            />
        );

        await screen.findByTestId("interview-reminder-form");
        expect(screen.getByDisplayValue("Иван Иванов")).toBeInTheDocument();
        expect(screen.getByDisplayValue("Логист")).toBeInTheDocument();
        expect(screen.getByDisplayValue("2026-08-21")).toBeInTheDocument();
        expect(screen.getByDisplayValue("10:00-11:00")).toBeInTheDocument();
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
                event_date: "2026-08-21",
                telegram_user: "@hr_petrov",
            })
        );
        expect(createEvent.mock.calls[0][0].note).toContain("Логист");
        expect(onSaved).toHaveBeenCalled();
    });
});
