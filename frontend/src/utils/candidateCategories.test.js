import {
    categoryFromCandidate,
    deadlineHighlight,
    daysBetween,
} from "./candidateCategories";

describe("candidateCategories", () => {
    it("maps stage and status to TZ categories", () => {
        expect(categoryFromCandidate({ stage: "нанят" })).toBe("staff");
        expect(categoryFromCandidate({ stage: "архивирован" })).toBe("archive");
        expect(categoryFromCandidate({ status: "отказ" })).toBe("archive");
        expect(categoryFromCandidate({ status: "ВНР" })).toBe("staff");
        expect(categoryFromCandidate({ stage: "в процессе найма" })).toBe("candidate");
    });

    it("highlights deadlines per TZ rules", () => {
        const today = new Date("2026-08-13T12:00:00");
        expect(deadlineHighlight("2026-08-10", today)).toBe("overdue");
        expect(deadlineHighlight("2026-08-15", today)).toBe("warning");
        expect(deadlineHighlight("2026-09-01", today)).toBe("ok");
        expect(deadlineHighlight(null, today)).toBeNull();
    });

    it("computes days in status", () => {
        const now = new Date("2026-08-13T12:00:00");
        expect(daysBetween("2026-08-10T00:00:00", now)).toBe(3);
    });
});
