/**
 * @jest-environment jsdom
 */
import { adaptationFormAbsoluteUrl, employeeTakeLinks, rememberAdaptationTake, readAdaptationTake, ADAPTATION_TAKE_STORAGE_KEY } from "./takeLinks";

describe("adaptation take links", () => {
    it("tolerates blocked browser storage", () => {
        const storage = {
            setItem: () => { throw new Error("QuotaExceededError"); },
            getItem: () => { throw new Error("SecurityError"); },
        };
        expect(rememberAdaptationTake({ token: "abc" }, storage)).toBeNull();
        expect(readAdaptationTake(storage)).toBeNull();
    });
    beforeEach(() => {
        window.localStorage.clear();
    });

    it("builds a public form url and remembers employee id", () => {
        expect(adaptationFormAbsoluteUrl("abc", "https://hr.example")).toBe("https://hr.example/adaptation/forms/abc");
        rememberAdaptationTake({ employee_id: 55, enrollment_id: 3, token: "abc" });
        expect(readAdaptationTake().employeeId).toBe(55);
        expect(JSON.parse(window.localStorage.getItem(ADAPTATION_TAKE_STORAGE_KEY)).enrollmentId).toBe(3);
    });

    it("keeps only employee take links for compact copy", () => {
        const links = [
            { role: "hr", token: "h" },
            { role: "employee", token: "e1" },
            { role: "manager", token: "m" },
        ];
        expect(employeeTakeLinks(links).map((item) => item.token)).toEqual(["e1"]);
    });
});
