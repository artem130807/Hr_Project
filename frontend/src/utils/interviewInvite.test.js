import {
    applyOfferLetterHeading,
    buildInterviewInviteText,
    formatInterviewDateTime,
    greetingNameFromFullName,
    OFFER_LETTER_HEADING,
} from "./interviewInvite";

describe("interviewInvite helpers", () => {
    it("takes name and patronymic from full name", () => {
        expect(greetingNameFromFullName("Иванов Артём Валерьевич")).toBe("Артём Валерьевич");
        expect(greetingNameFromFullName("Петрова Анна")).toBe("Анна");
    });

    it("formats date as '9 июля в 16:00'", () => {
        expect(formatInterviewDateTime("2026-07-09", "16:00")).toBe("9 июля в 16:00");
    });

    it("builds interview letter with contact block", () => {
        const text = buildInterviewInviteText({
            fullName: "Иванов Артём Валерьевич",
            dateValue: "2026-07-09",
            timeValue: "16:00",
            contactPhone: "8 902 001 37 28",
            contactName: "Кудряшова Светлана Алексеевна",
        });
        expect(text).toContain("Артём Валерьевич, здравствуйте!");
        expect(text).toContain("Приглашаем вас на собеседование");
        expect(text).toContain("Формат: очный");
        expect(text).toContain("Дата и время: 9 июля в 16:00");
        expect(text).toContain("8 902 001 37 28");
        expect(text).toContain("Кудряшова Светлана Алексеевна");
        expect(text).not.toMatch(/^Собеседование/m);
    });

    it("replaces interview heading on offer letters", () => {
        expect(applyOfferLetterHeading("Собеседование:\nТекст оффера")).toBe(
            `${OFFER_LETTER_HEADING}\n\nТекст оффера`
        );
    });

    it("builds candidate reminder text and default send time", () => {
        const {
            buildCandidateInterviewReminderText,
            defaultCandidateReminderAt,
            candidateReminderAtIso,
            CANDIDATE_INTERVIEW_REMINDER_QUESTION,
        } = require("./interviewInvite");
        expect(CANDIDATE_INTERVIEW_REMINDER_QUESTION).toContain("кандидата");
        expect(defaultCandidateReminderAt("2026-07-09", "16:00")).toBe("2026-07-09T15:00");
        expect(candidateReminderAtIso("2026-07-09T15:00")).toBe("2026-07-09T15:00:00");
        const text = buildCandidateInterviewReminderText({
            fullName: "Иванов Артём Валерьевич",
            dateValue: "2026-07-09",
            timeValue: "16:00",
        });
        expect(text).toContain("Артём Валерьевич, здравствуйте!");
        expect(text).toContain("Напоминаем о собеседовании.");
        expect(text).toContain("9 июля в 16:00");
    });
});
