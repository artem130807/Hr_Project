/**
 * @jest-environment jsdom
 */
import {
    formatMinutes,
    indexToSigned,
    signedLevel,
    toPsychReportModel,
} from "./psychReportViewModel";

describe("psychReportViewModel", () => {
    it("maps 0–100 index to signed −100…+100 display", () => {
        expect(indexToSigned(53)).toBe(6);
        expect(indexToSigned(48.5)).toBe(-3);
        expect(indexToSigned(86)).toBe(72);
        expect(signedLevel(72)).toBe("Выражено в положительном направлении");
        expect(signedLevel(6)).toBe("Близко к центру шкалы");
        expect(formatMinutes(1680)).toBe("28 минут");
        expect(formatMinutes(60)).toBe("1 минута");
        expect(formatMinutes(120)).toBe("2 минуты");
    });

    it("builds a report model from scored payload", () => {
        const model = toPsychReportModel({
            full_name: "Кудряшова Светлана Алексеевна",
            position: "Менеджер по персоналу",
            taken_at: "2026-04-20",
            birth_date: "1998-08-12",
            chs: 3,
            chm: 2,
            quality_status: "Приемлемый протокол",
            scores: {
                quality: { active_duration_sec: 1680, status: "Приемлемый протокол" },
                avp: {
                    factors: [
                        { code: "E", name: "Экстраверсия", score: 53 },
                        { code: "A", score: 48.5 },
                        { code: "C", score: 42 },
                        { code: "ES", score: 47 },
                        { code: "O", score: 86 },
                    ],
                    aspects: [
                        { code: "Oi", name: "Интеллект", score: 94 },
                        { code: "Ci", name: "Трудолюбие", score: 65.5 },
                        { code: "Oo", name: "Открытость", score: 78 },
                    ],
                },
                disc: {
                    "В работе": [
                        { code: "D", raw: 4 },
                        { code: "I", raw: -1 },
                        { code: "S", raw: -5 },
                        { code: "C", raw: 2 },
                    ],
                    "Под давлением": [{ code: "D", raw: 7 }, { code: "I", raw: -4 }],
                    Личное: [{ code: "D", raw: 4 }],
                },
                paei: [
                    { code: "P", name: "Производитель результата", count: 5 },
                    { code: "A", count: 4 },
                    { code: "E", name: "Предприниматель", count: 6 },
                    { code: "I", count: 3 },
                ],
                sjt: { quality_index: 79.2 },
            },
        });

        expect(model.qualityTone).toBe("good");
        expect(model.activeTime).toBe("28 минут");
        expect(model.behaviorPreference.label).toBe("решительность");
        expect(model.managementFocus.label).toBe("изменения и возможности");
        expect(model.factors.find((f) => f.code === "O").signed).toBe(72);
        expect(model.qualityIndex).toBe(79);
        expect(model.chs).toBe(3);
        expect(model.chm).toBe(2);
        expect(model.insight.text).toMatch(/Интеллектуальная вовлечённость/);
        expect(model.insight.tags).toContain("Интеллектуальная вовлечённость +88");
        expect(model.insight.text).toContain("внутреннем пилотном SJT");
        expect(model.insight.text).not.toMatch(/DISC|PAEI|ведущий тип/i);
    });
});
