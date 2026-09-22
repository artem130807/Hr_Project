import { EVENT_TYPE_OPTIONS, eventTypeRequiresEmployeeName, formatRepeatInterval, getEventTypeMeta } from "./eventTypes";

describe("eventTypes", () => {
    test("contains interview option", () => {
        expect(EVENT_TYPE_OPTIONS.some((x) => x.value === "interview")).toBe(true);
    });

    test("interview does not use employee field", () => {
        expect(eventTypeRequiresEmployeeName("interview")).toBe(false);
    });

    test("contains permanent option", () => {
        expect(EVENT_TYPE_OPTIONS.some((x) => x.value === "permanent")).toBe(true);
    });

    test("permanent does not use employee field", () => {
        expect(eventTypeRequiresEmployeeName("permanent")).toBe(false);
    });

    test("formats repeat interval", () => {
        expect(formatRepeatInterval(1, "month")).toBe("каждый месяц");
        expect(formatRepeatInterval(2, "week")).toBe("каждые 2 нед.");
    });

    test("returns interview visual meta", () => {
        const meta = getEventTypeMeta("interview");
        expect(meta.label).toBe("Собеседование");
        expect(meta.icon).toBeTruthy();
    });

    test("returns permanent visual meta", () => {
        expect(getEventTypeMeta("permanent").label).toBe("Постоянное");
    });
});
