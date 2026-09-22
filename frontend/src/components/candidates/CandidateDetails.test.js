/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import React from "react";
import { render, screen } from "@testing-library/react";
import CandidateDetails from "./CandidateDetails";

jest.mock("../../context/AlertContext", () => ({
    useAlertContext: () => ({ showAlert: jest.fn() }),
}));
jest.mock("../../services/candidateApi", () => ({
    assignVacancyToCandidate: jest.fn(() => Promise.resolve({})),
    sendCandidateNotification: jest.fn(() => Promise.resolve({})),
    updateCandidateStatus: jest.fn(() => Promise.resolve({})),
    archiveCandidate: jest.fn(() => Promise.resolve({})),
    getCandidateStatus: jest.fn(() => Promise.resolve({ status: "откликнулся" })),
    sendOffer: jest.fn(() => Promise.resolve({})),
    getCandidateById: jest.fn(() => Promise.resolve({})),
    getTestResults: jest.fn(() => Promise.resolve([])),
    getCandidateActiveVacancy: jest.fn(() => Promise.resolve(null)),
}));
jest.mock("../../services/vacancyApi", () => ({ getVacancies: jest.fn(() => Promise.resolve([])) }));
jest.mock("../../services/blacklistApi", () => ({ blockCandidate: jest.fn() }));
jest.mock("./CandidateStatusControls", () => () => null);
jest.mock("../tests/TestResultAccordionItem", () => () => null);
jest.mock("./OfferModal", () => () => null);
jest.mock("./CandidateTimeline", () => () => null);

const base = {
    id: 1,
    full_name: "Иван Тестов",
    status: "откликнулся",
    hh_resume_link: "https://hh.ru/resume/1",
    stage: "employment",
};

describe("CandidateDetails AI block", () => {
    it("shows placeholder when score is missing", () => {
        render(<CandidateDetails candidate={{ ...base }} />);
        expect(screen.getByTestId("candidate-ai-score")).toHaveTextContent("—");
        expect(screen.getByTestId("candidate-ai-comment")).toHaveTextContent("Комментария AI пока нет.");
        expect(screen.getByText("/ 100")).toBeInTheDocument();
    });

    it("shows score and comment from backend", () => {
        render(
            <CandidateDetails
                candidate={{ ...base, ai_score: 87, ai_comment: "Сильный профиль водителя." }}
            />
        );
        expect(screen.getByTestId("candidate-ai-score")).toHaveTextContent("87");
        expect(screen.getByTestId("candidate-ai-comment")).toHaveTextContent("Сильный профиль водителя.");
    });
});
