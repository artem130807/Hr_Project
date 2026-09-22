/**
 * @jest-environment node
 */
import {
    PSYCH_TAKE_DRAFT_TTL_MS,
    clearPsychTakeDraft,
    memoryStorage,
    psychTakeDraftKey,
    psychTakeDraftScopeFromSearch,
    readPsychTakeDraft,
    sanitizePsychTakeDraft,
    writePsychTakeDraft,
} from "./psychTakeDraft";

describe("psychTakeDraft", () => {
    const codes = ["AVP-001", "DISC-01"];

    it("scopes keys by instrument and optional result/candidate", () => {
        expect(psychTakeDraftScopeFromSearch("?candidate_id=6&result_id=2")).toBe("2");
        expect(psychTakeDraftScopeFromSearch("")).toBe("anon");
        expect(psychTakeDraftKey("complex_work_profile", "anon")).toBe(
            "psych-take-draft:v1:complex_work_profile:anon"
        );
    });

    it("round-trips answers and question index", () => {
        const storage = memoryStorage();
        writePsychTakeDraft(
            "complex_work_profile",
            {
                seed: 42,
                codes,
                answers: { "AVP-001": 4 },
                questionIndex: 1,
                fullName: "Иванов",
                position: "Логист",
                birthDate: "1998-01-01",
                startedAt: 100,
                activeMs: 50,
                latencies: { "AVP-001": 12 },
            },
            { storage, now: 1000 }
        );
        const draft = readPsychTakeDraft("complex_work_profile", { storage, itemCodes: codes, now: 1000 });
        expect(draft.answers["AVP-001"]).toBe(4);
        expect(draft.questionIndex).toBe(1);
        expect(draft.fullName).toBe("Иванов");
        expect(draft.seed).toBe(42);
    });

    it("drops expired and mismatched instrument drafts", () => {
        expect(
            sanitizePsychTakeDraft(
                { codes, answers: {}, savedAt: 1, questionIndex: 0 },
                { itemCodes: codes, now: 1 + PSYCH_TAKE_DRAFT_TTL_MS + 1 }
            )
        ).toBeNull();
        expect(
            sanitizePsychTakeDraft(
                { codes: ["OLD"], answers: {}, savedAt: 10, seed: 1 },
                { itemCodes: codes, now: 10 }
            )
        ).toBeNull();
    });

    it("clears storage", () => {
        const storage = memoryStorage();
        writePsychTakeDraft("x", { codes: [], answers: {} }, { storage, now: 1 });
        clearPsychTakeDraft("x", { storage });
        expect(readPsychTakeDraft("x", { storage, now: 1 })).toBeNull();
    });
});
