/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ExerciseModal from "./ExerciseModal";

jest.mock("../../context/AlertContext", () => ({
    useAlertContext: () => ({ showAlert: jest.fn() }),
}));

jest.mock("../../services/testApi", () => ({
    getTests: jest.fn(),
}));

jest.mock("../../services/candidateApi", () => ({
    sendProfessionalTestToCandidate: jest.fn(),
    loadCandidateVacancyTitle: jest.fn(),
}));

const { getTests } = require("../../services/testApi");
const { sendProfessionalTestToCandidate, loadCandidateVacancyTitle } = require("../../services/candidateApi");

describe("ExerciseModal professional test send", () => {
    beforeEach(() => {
        getTests.mockReset();
        sendProfessionalTestToCandidate.mockReset();
        loadCandidateVacancyTitle.mockReset();
        getTests.mockResolvedValue([
            { id: 11, name: "Тест логиста", test_type: "Вопросно-ответная форма" },
            { id: 22, name: "Псих тест", test_type: "url" },
        ]);
        sendProfessionalTestToCandidate.mockResolvedValue({ status: "ok", delivery: "sent" });
        loadCandidateVacancyTitle.mockResolvedValue(null);
    });

    test("loads professional tests and sends selected test", async () => {
        const onClose = jest.fn();
        const onSuccess = jest.fn();
        render(
            <ExerciseModal
                candidate={{ id: 5, full_name: "Иван Иванов", vacancy_name: "Логист" }}
                onClose={onClose}
                onSuccess={onSuccess}
            />
        );

        expect(await screen.findByText("Отправить профессиональный тест")).toBeInTheDocument();
        await screen.findByRole("option", { name: "Тест логиста" });
        const select = screen.getByLabelText("Профессиональный тест");
        fireEvent.change(select, { target: { value: "11" } });
        await waitFor(() => expect(select).toHaveValue("11"));
        fireEvent.change(screen.getByPlaceholderText(/стандартный текст/i), {
            target: { value: "Пройдите тест, пожалуйста" },
        });
        await waitFor(() => expect(screen.getByText("Отправить тест")).not.toBeDisabled());
        fireEvent.click(screen.getByText("Отправить тест"));

        await waitFor(() => expect(sendProfessionalTestToCandidate).toHaveBeenCalled());
        expect(sendProfessionalTestToCandidate).toHaveBeenCalledWith(5, 11, "Пройдите тест, пожалуйста");
        expect(onSuccess).toHaveBeenCalled();
        expect(onClose).toHaveBeenCalled();
    });

    test("loads vacancy the candidate applied to when calendar stub has no title", async () => {
        loadCandidateVacancyTitle.mockResolvedValue("Водитель категории C");
        render(
            <ExerciseModal
                candidate={{ id: 8, full_name: "Пётр Петров" }}
                onClose={jest.fn()}
            />
        );

        expect(await screen.findByText("Водитель категории C")).toBeInTheDocument();
        expect(loadCandidateVacancyTitle).toHaveBeenCalledWith(8);
        expect(screen.queryByText("Вакансия не указана")).not.toBeInTheDocument();
    });
});
