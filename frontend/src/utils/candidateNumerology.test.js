import { getCandidateNumerology } from "./candidateNumerology";

describe("getCandidateNumerology", () => {
    test("calculates CS and CM for dotted date example", () => {
        const out = getCandidateNumerology("12.34.5678");
        expect(out.cs).toBe(3); // 1+2
        expect(out.cm).toBe(9); // 1+2+3+4+5+6+7+8=36 -> 9
    });

    test("calculates CS for second example", () => {
        const out = getCandidateNumerology("98.76.5432");
        expect(out.cs).toBe(8); // 9+8=17 -> 8
    });

    test("supports ISO date", () => {
        const out = getCandidateNumerology("2026-08-21");
        expect(out.cs).toBe(3); // 2+1
        expect(out.cm).toBe(3); // 2+1+0+8+2+0+2+6=21 -> 3
    });

    test("returns nulls for empty date", () => {
        expect(getCandidateNumerology("")).toEqual({ cs: null, cm: null });
    });
});
