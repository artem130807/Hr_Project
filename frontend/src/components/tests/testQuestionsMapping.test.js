/**
 * Unit tests for test question form helpers (logic mirrored from TestForm).
 */
const normalizeQuestions = (list) =>
    (Array.isArray(list) ? list : []).map((q) => ({
        id: q?.id,
        question_text: String(q?.question_text || q?.text || ""),
        options: Array.isArray(q?.options) ? q.options : [],
    }));

const questionsPayload = (list) =>
    (Array.isArray(list) ? list : [])
        .map((q) => ({ text: String(q?.text || q?.question_text || "").trim() }))
        .filter((q) => q.text);

describe("test question form mapping", () => {
    it("hydrates API text into question_text for the edit form", () => {
        const out = normalizeQuestions([
            { id: 1, text: "Что вы знаете о компании?", test_id: 3 },
        ]);
        expect(out).toEqual([
            {
                id: 1,
                question_text: "Что вы знаете о компании?",
                options: [],
            },
        ]);
    });

    it("builds API payload from form question_text", () => {
        expect(
            questionsPayload([
                { question_text: "  Q1  " },
                { question_text: "   " },
                { text: "Q2" },
            ])
        ).toEqual([{ text: "Q1" }, { text: "Q2" }]);
    });
});
