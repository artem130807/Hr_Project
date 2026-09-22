/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import CandidateList from "./CandidateList";
import { HR_INTERVIEW_REMINDER_QUESTION } from "../../utils/interviewReminder";

jest.mock("../../context/AlertContext", () => ({
    useAlertContext: () => ({ showAlert: jest.fn() }),
}));

jest.mock("../../context/AuthContext", () => ({
    useAuth: () => ({ user: { name: "Кудряшова Светлана Алексеевна", erp_user_id: "hr-1" } }),
}));

jest.mock("./OfferModal", () => () => null);

jest.mock("../../services/testApi", () => ({
    getTests: jest.fn(() => Promise.resolve([])),
}));

jest.mock("../../services/candidateApi", () => ({
    sendOffer: jest.fn(),
    applyCandidateStatus: jest.fn(),
    updateCandidate: jest.fn(),
    sendProfessionalTestToCandidate: jest.fn(),
    sendInterviewInvite: jest.fn(),
    getCandidate: jest.fn(),
    loadCandidateVacancyTitle: jest.fn(),
}));

jest.mock("../../services/eventsApi", () => ({
    createEvent: jest.fn(),
    searchEventEmployees: jest.fn(),
}));

const {
    sendInterviewInvite,
    getCandidate,
    loadCandidateVacancyTitle,
} = require("../../services/candidateApi");
const { createEvent, searchEventEmployees } = require("../../services/eventsApi");

describe("CandidateList interview invite calendar post", () => {
    const candidate = {
        id: 5,
        full_name: "Иван Иванов",
        status: "откликнулся",
        stage: "в процессе найма",
    };

    beforeEach(() => {
        jest.clearAllMocks();
        sendInterviewInvite.mockResolvedValue({ status: "ok", delivery: "sent" });
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
        window.confirm = jest.fn(() => true);
    });

    test("books HR calendar slot then asks to mention HR for the reminder", async () => {
        render(
            <CandidateList
                candidates={[candidate]}
                onCandidateDelete={jest.fn()}
                onCandidateEdit={jest.fn()}
                onCandidateClick={jest.fn()}
            />
        );

        fireEvent.click(screen.getByRole("button", { name: "На собеседование" }));
        expect(await screen.findByText("Пригласить на собеседование")).toBeInTheDocument();
        fireEvent.change(screen.getByTestId("interview-date"), { target: { value: "2026-08-21" } });
        fireEvent.change(screen.getByTestId("interview-time"), { target: { value: "10:00" } });
        fireEvent.click(screen.getByTestId("interview-send"));

        await waitFor(() => expect(sendInterviewInvite).toHaveBeenCalled());
        expect(sendInterviewInvite).toHaveBeenCalledWith(
            5,
            expect.objectContaining({
                hr_id: "hr-1",
                interview_date: "2026-08-21",
                start_time: "10:00",
                end_time: "11:00",
                book_calendar: true,
                remind_candidate: false,
            })
        );
        expect(window.confirm).toHaveBeenCalledWith(HR_INTERVIEW_REMINDER_QUESTION);

        await screen.findByTestId("interview-reminder-form");
        expect(screen.getByDisplayValue("Иван Иванов")).toBeInTheDocument();
        expect(screen.getByDisplayValue("Логист")).toBeInTheDocument();
        expect(screen.getByDisplayValue("10:00-11:00")).toBeInTheDocument();

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
        expect(createEvent.mock.calls[0][0].note).toContain("Иван Иванов");
        expect(createEvent.mock.calls[0][0].note).toContain("Логист");
    });

    test("does not open HR reminder form when the question is declined", async () => {
        window.confirm.mockReturnValue(false);
        render(
            <CandidateList
                candidates={[candidate]}
                onCandidateDelete={jest.fn()}
                onCandidateEdit={jest.fn()}
                onCandidateClick={jest.fn()}
            />
        );

        fireEvent.click(screen.getByRole("button", { name: "На собеседование" }));
        fireEvent.change(await screen.findByTestId("interview-date"), { target: { value: "2026-08-21" } });
        fireEvent.change(screen.getByTestId("interview-time"), { target: { value: "10:00" } });
        fireEvent.click(screen.getByTestId("interview-send"));

        await waitFor(() => expect(sendInterviewInvite).toHaveBeenCalled());
        expect(window.confirm).toHaveBeenCalledWith(HR_INTERVIEW_REMINDER_QUESTION);
        expect(screen.queryByTestId("interview-reminder-form")).not.toBeInTheDocument();
        expect(createEvent).not.toHaveBeenCalled();
    });
});
