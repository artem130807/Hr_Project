/**
 * @jest-environment jsdom
 */
import { localISODate } from "./psychDates";

describe("localISODate", () => {
    it("uses the local calendar day, not UTC", () => {
        const value = new Date(2026, 7, 24, 1, 0, 0);
        expect(localISODate(value)).toBe("2026-08-24");
    });
});
