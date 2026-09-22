import { formatDateRu, replaceIsoDatesInText } from "./dateFormat";

describe("dateFormat utils", () => {
    test("formats YYYY-MM-DD to DD.MM.YYYY", () => {
        expect(formatDateRu("2026-08-21")).toBe("21.08.2026");
    });

    test("keeps non-date text as is", () => {
        expect(formatDateRu("5 рабочих дней")).toBe("5 рабочих дней");
    });

    test("replaces ISO dates in text", () => {
        expect(replaceIsoDatesInText("Дата 2026-08-21, дедлайн 2026-09-01")).toBe(
            "Дата 21.08.2026, дедлайн 01.09.2026"
        );
    });
});
