/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import TestDetails from "./TestDetails";

const mockPrintProfessionalTestPdf = jest.fn();

jest.mock("../../utils/printPdf", () => ({
    printProfessionalTestPdf: (...args) => mockPrintProfessionalTestPdf(...args),
}));

describe("TestDetails PDF export", () => {
    beforeEach(() => {
        mockPrintProfessionalTestPdf.mockReset();
        mockPrintProfessionalTestPdf.mockResolvedValue({ pages: 1 });
    });

    it("renders questions with options and exports PDF", async () => {
        render(
            <TestDetails
                test={{
                    id: 42,
                    name: "Тест логиста",
                    test_type: "Вопросно-ответная форма",
                    results_type: "текстовый результат",
                    description: "Профтест",
                    questions: [
                        {
                            id: 1,
                            question_text: "Что такое логистика?",
                            options: ["Перевозки", "Бухгалтерия"],
                            correct_option_index: 0,
                        },
                    ],
                }}
                onClose={jest.fn()}
            />
        );

        expect(screen.getByText(/Что такое логистика/)).toBeInTheDocument();
        expect(screen.getByText("Перевозки")).toBeInTheDocument();
        expect(screen.getByText("верный ответ")).toBeInTheDocument();
        fireEvent.click(screen.getByTestId("prof-test-save-pdf"));
        await waitFor(() => {
            expect(mockPrintProfessionalTestPdf).toHaveBeenCalledWith({
                root: expect.any(Object),
                testName: "Тест логиста",
            });
        });
    });
});
