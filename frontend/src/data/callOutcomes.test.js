import { CALL_OUTCOMES, normalizeCallOutcome } from "./callOutcomes";

describe("callOutcomes", () => {
    it("covers HR statuses including pending", () => {
        expect(CALL_OUTCOMES.pending.label).toBe("Определяется");
        expect(CALL_OUTCOMES.interested.label).toBe("Интерес");
        expect(CALL_OUTCOMES.interview.label).toBe("Собеседование");
        expect(CALL_OUTCOMES.callback.label).toBe("Перезвон");
        expect(CALL_OUTCOMES.rejected.label).toBe("Отказ");
        expect(CALL_OUTCOMES.dropped.label).toBe("Сброс");
    });

    it("normalizes aliases and unknown values", () => {
        expect(normalizeCallOutcome("no_answer")).toBe("dropped");
        expect(normalizeCallOutcome("interest")).toBe("interested");
        expect(normalizeCallOutcome("rejected")).toBe("rejected");
        expect(normalizeCallOutcome("???")).toBe("pending");
        expect(normalizeCallOutcome(null)).toBe("pending");
    });
});
