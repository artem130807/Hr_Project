import { fromDateTimeLocal, toDateTimeLocal } from "./dateTimeLocal";

describe("dateTimeLocal", () => {
    it("round-trips a stored instant through the browser local timezone", () => {
        const source = "2026-09-11T08:30:00.000Z";
        expect(fromDateTimeLocal(toDateTimeLocal(source))).toBe(source);
    });

    it("returns empty values for absent or invalid input", () => {
        expect(toDateTimeLocal(null)).toBe("");
        expect(toDateTimeLocal("bad-date")).toBe("");
        expect(fromDateTimeLocal("")).toBeNull();
        expect(fromDateTimeLocal("bad-date")).toBeNull();
    });
});
