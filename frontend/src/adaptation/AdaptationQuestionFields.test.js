import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import AdaptationQuestionFields from "./AdaptationQuestionFields";
import { formatQuestionAnswer } from "./answerFormat";

describe("AdaptationQuestionFields", () => {
    it("renders a neutral numeric scale and exact special options", () => {
        render(
            <AdaptationQuestionFields
                questions={[{
                    id: "score",
                    text: "Оцените показатель",
                    type: "scale_na",
                    required: true,
                    hint: "1 — не помогает; 5 — помогает заметно",
                    special_options: [{ value: "insufficient_data", label: "недостаточно данных" }],
                }]}
                values={{}}
                onChange={() => {}}
                coreHistory={{}}
            />
        );

        expect(screen.getByRole("option", { name: "1" })).toBeInTheDocument();
        expect(screen.getByRole("option", { name: "5" })).toBeInTheDocument();
        expect(screen.queryByText("1 — очень слабо")).not.toBeInTheDocument();
        expect(screen.getByRole("option", { name: "недостаточно данных" })).toBeInTheDocument();
        expect(screen.getByText("1 — не помогает; 5 — помогает заметно")).toBeInTheDocument();
    });

    it("does not allow an exclusive multi option together with ordinary answers", () => {
        const onChange = jest.fn();
        const question = {
            id: "support",
            text: "Какая поддержка предоставлена?",
            type: "multi",
            options: ["обучение", "обратная связь", "поддержка не требовалась"],
            exclusive_options: ["поддержка не требовалась"],
        };
        const { rerender } = render(
            <AdaptationQuestionFields
                questions={[question]}
                values={{ support: ["обучение"] }}
                onChange={onChange}
                coreHistory={{}}
            />
        );

        fireEvent.click(screen.getByRole("checkbox", { name: "поддержка не требовалась" }));
        expect(onChange).toHaveBeenLastCalledWith("support", ["поддержка не требовалась"]);

        rerender(
            <AdaptationQuestionFields
                questions={[question]}
                values={{ support: ["поддержка не требовалась"] }}
                onChange={onChange}
                coreHistory={{}}
            />
        );
        fireEvent.click(screen.getByRole("checkbox", { name: "обратная связь" }));
        expect(onChange).toHaveBeenLastCalledWith("support", ["обратная связь"]);
    });

    it("shows human-readable values on the review screen", () => {
        const question = {
            type: "scale_na",
            special_options: [{ value: "not_applicable", label: "не применимо" }],
        };
        expect(formatQuestionAnswer(question, "not_applicable")).toBe("не применимо");
        expect(formatQuestionAnswer(question, 4)).toBe("4 из 5");
        expect(formatQuestionAnswer({ type: "multi" }, ["обучение", "доступы"])).toBe("обучение, доступы");
    });
});
