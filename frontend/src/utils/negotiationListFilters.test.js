import {
    EMPTY_NEGOTIATION_FILTERS,
    experienceFromMonths,
    filterNegotiationItems,
    hasNegotiationFilters,
    matchesNegotiationFilters,
} from "./negotiationListFilters";

const item = (overrides = {}, resume = {}) => ({
    id: "n1",
    viewed_by_opponent: true,
    has_updates: false,
    resume: {
        full_name: "Иванов",
        area: "Москва",
        age: 30,
        experience_months: 40,
        work_formats: [{ id: "REMOTE" }],
        ...resume,
    },
    ...overrides,
});

describe("negotiationListFilters", () => {
    it("maps months to HH experience buckets", () => {
        expect(experienceFromMonths(5)).toBe("noExperience");
        expect(experienceFromMonths(12)).toBe("between1And3");
        expect(experienceFromMonths(36)).toBe("between3And6");
        expect(experienceFromMonths(72)).toBe("moreThan6");
    });

    it("empty filters match everyone", () => {
        expect(matchesNegotiationFilters(item(), EMPTY_NEGOTIATION_FILTERS)).toBe(true);
        expect(hasNegotiationFilters(EMPTY_NEGOTIATION_FILTERS)).toBe(false);
    });

    it("filters by city containment", () => {
        expect(matchesNegotiationFilters(item(), { ...EMPTY_NEGOTIATION_FILTERS, city: "моск" })).toBe(true);
        expect(matchesNegotiationFilters(item(), { ...EMPTY_NEGOTIATION_FILTERS, city: "Казань" })).toBe(false);
        expect(
            matchesNegotiationFilters(item({}, { area: null }), { ...EMPTY_NEGOTIATION_FILTERS, city: "Москва" })
        ).toBe(false);
    });

    it("filters by age range", () => {
        expect(matchesNegotiationFilters(item(), { ...EMPTY_NEGOTIATION_FILTERS, age_from: "25", age_to: "35" })).toBe(true);
        expect(matchesNegotiationFilters(item(), { ...EMPTY_NEGOTIATION_FILTERS, age_from: "40" })).toBe(false);
        expect(matchesNegotiationFilters(item({}, { age: null }), { ...EMPTY_NEGOTIATION_FILTERS, age_to: "40" })).toBe(false);
    });

    it("treats experience as a minimum", () => {
        expect(matchesNegotiationFilters(item(), { ...EMPTY_NEGOTIATION_FILTERS, experience: "between1And3" })).toBe(true);
        expect(matchesNegotiationFilters(item(), { ...EMPTY_NEGOTIATION_FILTERS, experience: "moreThan6" })).toBe(false);
    });

    it("requires HH work format id", () => {
        expect(matchesNegotiationFilters(item(), { ...EMPTY_NEGOTIATION_FILTERS, work_format: "remote" })).toBe(true);
        expect(matchesNegotiationFilters(item(), { ...EMPTY_NEGOTIATION_FILTERS, work_format: "office" })).toBe(false);
        expect(matchesNegotiationFilters(item(), { ...EMPTY_NEGOTIATION_FILTERS, work_format: "shift" })).toBe(true);
    });

    it("combines unviewed with criteria", () => {
        const items = [
            item({ id: "a", viewed_by_opponent: false }),
            item({ id: "b", viewed_by_opponent: true }, { area: "Казань" }),
        ];
        const out = filterNegotiationItems(items, {
            onlyUnviewed: true,
            filters: { ...EMPTY_NEGOTIATION_FILTERS, city: "Москва" },
        });
        expect(out.map((i) => i.id)).toEqual(["a"]);
    });
});
