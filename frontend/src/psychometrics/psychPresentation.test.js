/**
 * @jest-environment jsdom
 */
import {
    applyPsychPresentation,
    blockNumber,
    createTakeSession,
    DEFAULT_PRESENTATION,
    normalizePresentation,
} from "./psychPresentation";

describe("psychPresentation", () => {
    const items = [
        { code: "DISC-01", module: "disc" },
        { code: "AVP-001", module: "avp" },
        { code: "AVP-002", module: "avp" },
        { code: "AVP-003", module: "avp" },
        { code: "SJT-01", module: "sjt" },
    ];

    it("defaults to 2-3-1 block order and AVP shuffle", () => {
        const spec = normalizePresentation(null);
        expect(spec.block_order).toEqual(DEFAULT_PRESENTATION.block_order);
        expect(spec.shuffle_modules).toEqual(["avp"]);
        expect(blockNumber("avp")).toBe(1);
        expect(blockNumber("sjt")).toBe(2);
        expect(blockNumber("disc")).toBe(3);
    });

    it("reorders modules even without a seed", () => {
        const shown = applyPsychPresentation(items, DEFAULT_PRESENTATION, undefined);
        expect(shown.map((it) => it.module)).toEqual(["avp", "avp", "avp", "sjt", "disc"]);
    });

    it("shuffles only AVP for a given seed", () => {
        const a = applyPsychPresentation(items, DEFAULT_PRESENTATION, 42).map((it) => it.code);
        const b = applyPsychPresentation(items, DEFAULT_PRESENTATION, 42).map((it) => it.code);
        const c = applyPsychPresentation(items, DEFAULT_PRESENTATION, 7).map((it) => it.code);
        expect(a).toEqual(b);
        expect(a.slice(-2)).toEqual(["SJT-01", "DISC-01"]);
        expect(new Set(a.slice(0, 3))).toEqual(new Set(["AVP-001", "AVP-002", "AVP-003"]));
        expect(a).not.toEqual(c);
    });

    it("reuses localStorage order on reload", () => {
        const storage = {
            data: {},
            getItem(key) {
                return this.data[key] || null;
            },
            setItem(key, value) {
                this.data[key] = value;
            },
            removeItem(key) {
                delete this.data[key];
            },
        };
        const instrument = { id: "complex_work_profile", items };
        const first = createTakeSession(instrument, storage, { sessionStore: null });
        const second = createTakeSession(instrument, storage, { sessionStore: null });
        expect(second.seed).toBe(first.seed);
        expect(second.items.map((it) => it.code)).toEqual(first.items.map((it) => it.code));
        expect(first.items[0].module).toBe("avp");
        expect(first.items[first.items.length - 1].module).toBe("disc");
    });
});
