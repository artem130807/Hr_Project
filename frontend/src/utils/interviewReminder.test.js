import { buildInterviewReminderNote, buildInterviewReminderFormState, interviewTimeRange, HR_INTERVIEW_REMINDER_QUESTION } from "./interviewReminder";

describe("buildInterviewReminderNote", () => {
    test("builds readable interview reminder note", () => {
        const note = buildInterviewReminderNote({
            candidateName: "Иван Иванов",
            vacancyName: "Логист",
            eventDate: "2026-08-21",
            interviewTime: "10:00-11:00",
            candidatePhone: "+79990000000",
            candidateEmail: "ivan@example.com",
            candidateTelegram: "@ivan567",
        });
        expect(note).toContain("Иван Иванов");
        expect(note).toContain("«Логист»");
        expect(note).toContain("21.08.2026");
        expect(note).toContain("10:00-11:00");
        expect(note).toContain("ivan@example.com");
        expect(note).toContain("+79990000000");
        expect(note).toContain("@ivan567");
    });

    test("builds time range and prefilled reminder form", () => {
        expect(interviewTimeRange("10:00:00", "11:00:00")).toBe("10:00-11:00");
        expect(HR_INTERVIEW_REMINDER_QUESTION).toBe("Создать напоминание о собеседовании для HR?");
        const form = buildInterviewReminderFormState({
            candidateName: "Иван Иванов",
            vacancyName: "Логист",
            eventDate: "2026-08-21",
            interviewTime: "10:00-11:00",
            remindAtTime: "10:00",
            candidatePhone: "+79990000000",
            candidateEmail: "ivan@example.com",
            candidateTelegram: "@ivan567",
        });
        expect(form.candidate_name).toBe("Иван Иванов");
        expect(form.vacancy_name).toBe("Логист");
        expect(form.event_date).toBe("2026-08-21");
        expect(form.remind_at_time).toBe("10:00");
        expect(form.note).toContain("Логист");
        expect(form.note).toContain("@ivan567");
    });
});
