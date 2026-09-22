import { documentFilename, isoDatePart, safeFilenamePart } from "./documentFilename";

describe("documentFilename", () => {
    it("builds a stable descriptive name from available document metadata", () => {
        expect(documentFilename({
            type: "Оценка кандидата",
            fullName: "Иванов Иван",
            position: "HR / BP",
            stage: "Интервью",
            date: "2026-09-10",
            id: 42,
        })).toBe("Оценка кандидата — Иванов Иван — HR BP — Интервью — 2026-09-10 — ID-42.pdf");
    });

    it("sanitizes file-system characters and tolerates invalid dates", () => {
        expect(safeFilenamePart('a/b:*?"<>|')).toBe("a b");
        expect(isoDatePart("not-a-date")).toBe("");
        expect(isoDatePart("10.09.2026")).toBe("2026-09-10");
        expect(documentFilename({ type: "Сотрудники", date: null, extension: "xlsx" })).toBe("Сотрудники.xlsx");
    });
});
