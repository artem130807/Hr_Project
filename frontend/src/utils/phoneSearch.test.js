/**
 * @jest-environment jsdom
 */
import { canonicalRuPhone, formatRuPhone, phoneMatches, isPhoneQuery } from "./phoneSearch";
import { filterCalls, formatCallDuration } from "./callFilters";

describe("phoneSearch", () => {
    it("canonicalizes 8 and 10-digit numbers to 7…", () => {
        expect(canonicalRuPhone("8 (999) 214-08-31")).toBe("79992140831");
        expect(canonicalRuPhone("9992140831")).toBe("79992140831");
        expect(canonicalRuPhone("+7 999 214-08-31")).toBe("79992140831");
    });

    it("formats display as +7 XXX XXX-XX-XX", () => {
        expect(formatRuPhone("89992140831")).toBe("+7 999 214-08-31");
    });

    it("matches a full number exactly, not a neighbour", () => {
        expect(phoneMatches("+7 999 214-08-31", "89992140831")).toBe(true);
        expect(phoneMatches("+7 903 214-08-31", "89992140831")).toBe(false);
    });

    it("treats 4+ digits as a phone query", () => {
        expect(isPhoneQuery("214")).toBe(false);
        expect(isPhoneQuery("2140")).toBe(true);
    });
});

describe("filterCalls", () => {
    const calls = [
        { id: "a", phone: "+7 999 214-08-31", operatorPhone: "+7 900 000-00-00", direction: "outgoing", outcome: "interested" },
        { id: "b", phone: "+7 903 214-08-31", operatorPhone: "+7 900 000-00-00", direction: "incoming", outcome: "interview" },
    ];
    const open = { allowedPhones: [] };

    it("filters by exact phone", () => {
        const found = filterCalls(calls, { ...open, phoneQuery: "+7 999 214-08-31" });
        expect(found.map((c) => c.id)).toEqual(["a"]);
    });

    it("matches the operator number", () => {
        const found = filterCalls(calls, { ...open, phoneQuery: "79000000000" });
        expect(found.map((c) => c.id)).toEqual(["a", "b"]);
    });

    it("filters by direction and outcome", () => {
        expect(filterCalls(calls, { ...open, direction: "incoming" }).map((c) => c.id)).toEqual(["b"]);
        expect(filterCalls(calls, { ...open, outcome: "interested" }).map((c) => c.id)).toEqual(["a"]);
    });

    it("does not filter while the number is still short", () => {
        expect(filterCalls(calls, { ...open, phoneQuery: "21" })).toHaveLength(2);
    });

    it("keeps only calls that involve the company line, regardless of spacing", () => {
        const mixed = [
            { id: "caller", phone: "+7 902 001 37 28", operatorPhone: "+7 900 000-00-00" },
            { id: "operator", phone: "+7 903 551-77-02", operatorPhone: "+79020013728" },
            { id: "other", phone: "+7 999 214-08-31", operatorPhone: "+7 900 000-00-00" },
        ];
        expect(filterCalls(mixed).map((c) => c.id)).toEqual(["caller", "operator"]);
    });

    it("formats duration", () => {
        expect(formatCallDuration(312)).toBe("5:12");
        expect(formatCallDuration(9)).toBe("0:09");
    });
});
