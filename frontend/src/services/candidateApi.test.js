jest.mock('../config/api', () => ({
    API_URL: 'http://api.test',
    API_PREFIX: '/v1',
}));

jest.mock('../utils/http', () => ({
    http: {
        get: jest.fn(),
        post: jest.fn(),
        patch: jest.fn(),
        put: jest.fn(),
        del: jest.fn(),
    },
}));

describe('candidateApi getCandidates pagination', () => {
    beforeEach(() => {
        jest.resetModules();
        const { http } = require('../utils/http');
        http.get.mockReset();
        http.get.mockResolvedValue({ items: [], total: 0, page: 1, per_page: 20, total_pages: 0 });
    });

    it('sends 1-based page and per_page to /candidates', async () => {
        const { http } = require('../utils/http');
        const { getCandidates } = require('./candidateApi');

        await getCandidates(null, 'Иван', null, 7, true, 2, 20, 'candidate');

        expect(http.get).toHaveBeenCalledWith(
            expect.stringMatching(/^\/candidates\?/),
            expect.any(Object)
        );
        const url = http.get.mock.calls[0][0];
        expect(url).toContain('page=3'); // 0-based page 2 → API page 3
        expect(url).toContain('per_page=20');
        expect(url).toContain('search=%D0%98%D0%B2%D0%B0%D0%BD');
        expect(url).toContain('vacancy_id=7');
        expect(url).toContain('is_perfect_candidate=true');
        expect(url).toContain('category=candidate');
    });

    it('omits empty optional filters', async () => {
        const { http } = require('../utils/http');
        const { getCandidates } = require('./candidateApi');

        await getCandidates();

        const url = http.get.mock.calls[0][0];
        expect(url).toContain('page=1');
        expect(url).toContain('per_page=20');
        expect(url).not.toContain('status=');
        expect(url).not.toContain('search=');
        expect(url).not.toContain('vacancy_id=');
    });
});

describe("candidateApi professional tests", () => {
    beforeEach(() => {
        const { http } = require("../utils/http");
        http.post.mockReset();
        http.post.mockResolvedValue({ status: "ok" });
    });

    it("sends professional test request to candidate endpoint", async () => {
        const { http } = require("../utils/http");
        const { sendProfessionalTestToCandidate } = require("./candidateApi");

        await sendProfessionalTestToCandidate(5, 11);
        expect(http.post).toHaveBeenCalledWith("/candidate/professional-test/send", {
            candidate_id: 5,
            test_id: 11,
        });
    });

    it("sends interview invite with calendar fields", async () => {
        const { http } = require("../utils/http");
        const { sendInterviewInvite } = require("./candidateApi");
        await sendInterviewInvite(5, {
            message: "Приглашаем вас на собеседование",
            hr_id: "hr-1",
            interview_date: "2026-07-09",
            start_time: "16:00",
            end_time: "17:00",
        });
        expect(http.post).toHaveBeenCalledWith("/candidate/interview-invite", {
            candidate_id: 5,
            message: "Приглашаем вас на собеседование",
            hr_id: "hr-1",
            interview_date: "2026-07-09",
            start_time: "16:00",
            end_time: "17:00",
            book_calendar: true,
            remind_candidate: false,
            remind_at: null,
            reminder_message: null,
        });
    });
});

describe("candidateApi hire routing", () => {
    beforeEach(() => {
        const { http } = require("../utils/http");
        http.put.mockReset();
        http.put.mockResolvedValue({ id: 5, stage: "нанят" });
    });

    it("applyCandidateStatus routes ВНР to hire endpoint", async () => {
        const { http } = require("../utils/http");
        const { applyCandidateStatus } = require("./candidateApi");
        await applyCandidateStatus(5, "ВНР");
        expect(http.put).toHaveBeenCalledWith("/candidate/5/hire");
    });
});

describe("candidateApi status catalog and vacancy changes", () => {
    beforeEach(() => {
        const { http } = require("../utils/http");
        http.get.mockReset();
        http.post.mockReset();
    });

    it("keeps backend code but exposes canonical presentation metadata", async () => {
        const { http } = require("../utils/http");
        const { getCandidatesStatuses } = require("./candidateApi");
        http.get.mockResolvedValue({ items: [{
            status: "Full documents",
            label: "Полный пакет документов",
            stage: "Оформление",
            state: "Документы собраны",
            next_action: "Подтвердить выход на работу",
            allowed_transitions: ["ВНР"],
        }] });
        await expect(getCandidatesStatuses()).resolves.toEqual([expect.objectContaining({
            code: "Full documents",
            name: "Полный пакет документов",
            stage: "Оформление",
            state: "Документы собраны",
            nextAction: "Подтвердить выход на работу",
            allowedTransitions: ["ВНР"],
        })]);
    });

    it("uses the atomic vacancy change endpoint", async () => {
        const { http } = require("../utils/http");
        const { changeCandidateVacancy } = require("./candidateApi");
        http.post.mockResolvedValue({});
        await changeCandidateVacancy(5, 12);
        expect(http.post).toHaveBeenCalledWith("/candidate/vacancy/change", {
            candidate_id: 5,
            vacancy_id: 12,
        });
    });
});

describe("candidateApi loadCandidateVacancyTitle", () => {
    beforeEach(() => {
        const { http } = require("../utils/http");
        http.get.mockReset();
    });

    it("returns active vacancy name", async () => {
        const { http } = require("../utils/http");
        const { loadCandidateVacancyTitle } = require("./candidateApi");
        http.get.mockResolvedValueOnce({ name: "Логист", hh_vacancy_id: "55" });

        await expect(loadCandidateVacancyTitle(5)).resolves.toBe("Логист");
        expect(http.get).toHaveBeenCalledWith("/candidate/5/active-vacancy");
    });

    it("falls back to latest linked vacancy when active is missing", async () => {
        const { http } = require("../utils/http");
        const { loadCandidateVacancyTitle } = require("./candidateApi");
        http.get
            .mockRejectedValueOnce(new Error("Vacancy not found"))
            .mockResolvedValueOnce([
                { id: 1, is_active: false, vacancy: { name: "Старая" } },
                { id: 4, is_active: false, vacancy: { name: "Водитель" } },
            ]);

        await expect(loadCandidateVacancyTitle(8)).resolves.toBe("Водитель");
        expect(http.get).toHaveBeenNthCalledWith(2, "/candidate/8/vacancies");
    });
});
