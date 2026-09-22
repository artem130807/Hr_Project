/** @jest-environment jsdom */
import "@testing-library/jest-dom";
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AdaptationPublicFormPage from "./AdaptationPublicFormPage";
import { getPublicAdaptationForm, submitPublicAdaptationForm } from "../services/adaptationApi";

jest.mock("react-router-dom", () => ({ useParams: () => ({ token: "personal-token" }) }), { virtual: true });
jest.mock("../services/adaptationApi", () => ({
    getPublicAdaptationForm: jest.fn(),
    submitPublicAdaptationForm: jest.fn(),
}));
jest.mock("../adaptation/AdaptationQuestionFields", () => ({ onChange }) => (
    <button type="button" onClick={() => onChange("core_e1", 5)}>Заполнить</button>
));

describe("AdaptationPublicFormPage", () => {
    afterEach(() => jest.restoreAllMocks());

    it("loads and submits when localStorage is unavailable", async () => {
        jest.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
            throw new Error("QuotaExceededError");
        });
        render(<AdaptationPublicFormPage />);
        expect(await screen.findByText("Опрос 1 месяц")).toBeInTheDocument();
        fireEvent.click(screen.getByText("Заполнить"));
        fireEvent.click(screen.getByRole("button", { name: "Отправить ответы" }));
        fireEvent.click(await screen.findByRole("button", { name: "Подтвердить и отправить" }));
        expect(await screen.findByText("Спасибо! Ответы сохранены и переданы HR.")).toBeInTheDocument();
        expect(submitPublicAdaptationForm).toHaveBeenCalledTimes(1);
    });
    beforeEach(() => {
        jest.clearAllMocks();
        window.localStorage.clear();
        getPublicAdaptationForm.mockResolvedValue({
            title: "Опрос 1 месяц",
            questions: [{ id: "core_e1", text: "Оцените адаптацию" }],
            locked: false,
            employee_id: 55,
            enrollment_id: 3,
            checkpoint_id: 8,
            role: "employee",
            kind: "month_1",
        });
        submitPublicAdaptationForm.mockResolvedValue({ submitted: true });
    });

    it("loads token form and locks the successful submission", async () => {
        render(<AdaptationPublicFormPage />);
        expect(await screen.findByText("Опрос 1 месяц")).toBeInTheDocument();
        fireEvent.click(screen.getByText("Заполнить"));
        fireEvent.click(screen.getByRole("button", { name: "Отправить ответы" }));
        expect(await screen.findByText("Проверьте ответы перед отправкой")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Подтвердить и отправить" }));
        await waitFor(() => expect(submitPublicAdaptationForm).toHaveBeenCalledWith("personal-token", { core_e1: 5 }));
        expect(await screen.findByText("Спасибо! Ответы сохранены и переданы HR.")).toBeInTheDocument();
        expect(JSON.parse(window.localStorage.getItem("adaptationTake")).employeeId).toBe(55);
    });

    it("does not submit while a visible required answer is empty", async () => {
        render(<AdaptationPublicFormPage />);
        expect(await screen.findByText("Опрос 1 месяц")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Отправить ответы" }));
        expect(await screen.findByText(/Заполните обязательное поле/)).toBeInTheDocument();
        expect(submitPublicAdaptationForm).not.toHaveBeenCalled();
    });
});
