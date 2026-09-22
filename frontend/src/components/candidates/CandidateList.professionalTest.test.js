import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import CandidateList from "./CandidateList";

jest.mock("../../context/AlertContext", () => ({
    useAlertContext: () => ({ showAlert: jest.fn() }),
}));

jest.mock("../../context/AuthContext", () => ({
    useAuth: () => ({ user: { name: "Кудряшова Светлана Алексеевна", erp_user_id: "hr-1" } }),
}));

jest.mock("./CandidateQuickActions", () => () => <div data-testid="quick-actions" />);
jest.mock("./OfferModal", () => () => null);
jest.mock("./InterviewInviteModal", () => () => null);

jest.mock("../../services/testApi", () => ({
    getTests: jest.fn(),
}));

jest.mock("../../services/candidateApi", () => ({
    sendOffer: jest.fn(),
    applyCandidateStatus: jest.fn(),
    updateCandidate: jest.fn(),
    sendProfessionalTestToCandidate: jest.fn(),
    sendInterviewInvite: jest.fn(),
    loadCandidateVacancyTitle: jest.fn(() => Promise.resolve(null)),
    getCandidate: jest.fn(() => Promise.resolve({})),
}));

describe("CandidateList professional test send", () => {
    const candidate = {
        id: 5,
        full_name: "Иван Иванов",
        status: "откликнулся",
        stage: "в процессе найма",
    };

    beforeEach(() => {
        jest.clearAllMocks();
        const { getTests } = require("../../services/testApi");
        getTests.mockResolvedValue([
            { id: 11, name: "Проф тест", test_type: "Вопросно-ответная форма" },
            { id: 12, name: "URL тест", test_type: "url" },
        ]);
    });

    it("opens modal, shows only professional tests and sends selected test", async () => {
        const { sendProfessionalTestToCandidate } = require("../../services/candidateApi");
        sendProfessionalTestToCandidate.mockResolvedValue({ status: "ok" });

        render(
            <CandidateList
                candidates={[candidate]}
                onCandidateDelete={jest.fn()}
                onCandidateEdit={jest.fn()}
                onCandidateClick={jest.fn()}
            />
        );

        fireEvent.click(screen.getByRole("button", { name: "Отправить тест" }));
        await waitFor(() => {
            expect(screen.getByText("Отправить профессиональный тест")).toBeInTheDocument();
        });
        await waitFor(() => {
            expect(screen.getByText("Проф тест")).toBeInTheDocument();
        });
        expect(screen.queryByText("URL тест")).not.toBeInTheDocument();

        fireEvent.change(screen.getByLabelText("Профессиональный тест"), { target: { value: "11" } });
        fireEvent.click(screen.getAllByRole("button", { name: "Отправить тест" }).at(-1));

        await waitFor(() => {
            expect(sendProfessionalTestToCandidate).toHaveBeenCalledWith(5, 11, null);
        });
    });
});
