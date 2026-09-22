/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import PsychResultPdfDocument from "../components/psych/PsychResultPdfDocument";
import { toPsychReportModel } from "./psychReportViewModel";

describe("PsychResultPdfDocument", () => {
    it("renders the full profile card content for PDF export", () => {
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
                    aspects: [{ code: "Oi", name: "Интеллект", score: 94 }],
                },
                disc: {
                    "В работе": [
                        { code: "D", raw: 4 },
                        { code: "I", raw: -1 },
                        { code: "S", raw: -5 },
                        { code: "C", raw: 2 },
                    ],
                    "Под давлением": [{ code: "D", raw: 7 }],
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

        render(<PsychResultPdfDocument model={model} />);
        const doc = screen.getByTestId("psych-pdf-document");
        expect(doc).toHaveTextContent("Кудряшова Светлана Алексеевна");
        expect(doc).toHaveTextContent("Пять факторов BFAS");
        expect(doc).toHaveTextContent("Экстраверсия");
        expect(doc).toHaveTextContent("Объединяет энтузиазм и ассертивность");
        expect(doc).toHaveTextContent("внутренний пилотный поведенческий блок");
        expect(doc).toHaveTextContent("В работе");
        expect(doc).toHaveTextContent("Под давлением");
        expect(doc).toHaveTextContent("Личное");
        expect(doc).toHaveTextContent("Решительность, прямота и контроль результата.");
        expect(doc).toHaveTextContent("внутренний SJT, пилотная версия");
        expect(doc).toHaveTextContent("Ориентация на возможности");
        expect(doc).toHaveTextContent("Наблюдения для интервью");
        expect(doc).toHaveTextContent("Соответствие экспертному ключу: 79 из 100");
        expect(doc).toHaveTextContent("75–100 по экспертному ключу");
        expect(doc).toHaveTextContent("не являются диагнозом");
        expect(doc).toHaveTextContent("не являются диагнозом, выводом о пригодности");
        expect(doc).not.toHaveTextContent(/DISC|PAEI|ведущий тип|Производитель результата|Администратор|Предприниматель|Интегратор/i);
    });
});
