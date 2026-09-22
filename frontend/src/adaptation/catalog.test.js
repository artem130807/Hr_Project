/**
 * @jest-environment node
 */
import { formFor, formPublicTitle, normalizeQuestionnaire } from "./catalog";
import { isQuestionVisible } from "./showIf";

describe("approved adaptation catalog", () => {
    it("starts employee forms with the five core scales", () => {
        expect(formFor("week_1", "employee")[0].id).toBe("core_e1");
        expect(formFor("month_1", "employee").some((q) => q.id === "core_e5")).toBe(true);
        expect(formFor("control_2m", "employee")).toEqual([]);
        expect(formFor("control_2m", "hr")[0].id).toBe("c2_confirm");
        expect(formFor("extra", "hr")[0].required).toBe(false);
        expect(formPublicTitle("extra", "employee")).toBe("Адаптационный опрос");
    });

    it("shows explain fields on low core scores or delta", () => {
        const q = formFor("week_1", "employee").find((item) => item.id === "core_e1_explain");
        expect(isQuestionVisible(q, { core_e1: 5 })).toBe(false);
        expect(isQuestionVisible(q, { core_e1: 2 })).toBe(true);
        expect(isQuestionVisible(q, { core_e1: 5 }, { core_e1: 3 })).toBe(true);
    });

    it("keeps the approved manager month options when the API payload is polluted", () => {
        const normalized = normalizeQuestionnaire("month_1", "manager", [
            {
                id: "mgr1_support",
                text: "устаревший текст",
                type: "multi",
                options: ["информирование задачи", "3", "пут"],
            },
            {
                id: "mgr1_risks",
                text: "устаревший текст",
                type: "multi",
                options: ["кабан", "ноя", "е-е-е"],
            },
        ]);

        const support = normalized.find((q) => q.id === "mgr1_support");
        const risks = normalized.find((q) => q.id === "mgr1_risks");
        expect(support.options).toEqual([
            "разъяснение задач",
            "обучение",
            "регулярная обратная связь",
            "наставник",
            "корректировка нагрузки",
            "дополнительные материалы или доступы",
            "поддержка не требовалась",
            "другое",
        ]);
        expect(support.exclusive_options).toEqual(["поддержка не требовалась"]);
        expect(risks.options).toContain("значимых рисков нет");
        expect(risks.options).not.toContain("кабан");
    });

    it("preserves the questionnaire composition supplied by the API", () => {
        const normalized = normalizeQuestionnaire("month_1", "manager", [
            { id: "mgr1_support", type: "multi", options: ["устаревшее значение"] },
            { id: "custom_module", text: "Дополнительный вопрос", type: "text" },
        ]);

        expect(normalized.map((q) => q.id)).toEqual(["mgr1_support", "custom_module"]);
        expect(normalized[0].options).toContain("разъяснение задач");
        expect(normalized[1]).toEqual({
            id: "custom_module",
            text: "Дополнительный вопрос",
            type: "text",
        });
    });

    it("returns isolated catalog copies so one form cannot corrupt another", () => {
        const first = formFor("month_1", "manager");
        first.find((q) => q.id === "mgr1_support").options.push("поврежденный вариант");

        const second = formFor("month_1", "manager");
        expect(second.find((q) => q.id === "mgr1_support").options).not.toContain("поврежденный вариант");
    });

    it("uses exact special scale choices from the approved questionnaires", () => {
        const employeeKpi = formFor("month_1", "employee").find((q) => q.id === "m1_kpi");
        const feedback = formFor("month_1", "employee").find((q) => q.id === "m1_fb_useful");
        const managerKpi = formFor("month_1", "manager").find((q) => q.id === "mgr1_kpi");

        expect(employeeKpi.special_options).toEqual([{ value: "not_applicable", label: "не применимо" }]);
        expect(feedback.special_options).toEqual([{ value: "insufficient_data", label: "недостаточно данных" }]);
        expect(managerKpi.special_options.map((item) => item.label)).toEqual([
            "не применимо",
            "недостаточно наблюдений",
        ]);
    });
});
