import { formatDateRu } from "./dateFormat";

export const HR_INTERVIEW_REMINDER_QUESTION =
    "Создать напоминание о собеседовании для HR?";

export function interviewTimeRange(startTime, endTime) {
    const start = String(startTime || "").slice(0, 5);
    const end = String(endTime || "").slice(0, 5);
    if (start && end) return `${start}-${end}`;
    return start || end || "";
}

export function buildInterviewReminderFormState({
    candidateName,
    vacancyName,
    eventDate,
    interviewTime,
    remindAtTime,
    candidatePhone,
    candidateEmail,
    candidateTelegram,
} = {}) {
    const note = buildInterviewReminderNote({
        candidateName,
        vacancyName,
        eventDate,
        interviewTime,
        candidatePhone,
        candidateEmail,
        candidateTelegram,
    });
    return {
        candidate_name: String(candidateName || "").trim(),
        vacancy_name: String(vacancyName || "").trim(),
        event_date: eventDate || "",
        interview_time: interviewTime || "",
        remind_before: 1,
        remind_at_time: String(remindAtTime || interviewTime || "").slice(0, 5),
        candidate_phone: String(candidatePhone || "").trim(),
        candidate_email: String(candidateEmail || "").trim(),
        candidate_telegram: String(candidateTelegram || "").trim(),
        telegram_user: "",
        note,
    };
}

export function buildInterviewReminderNote({
    candidateName,
    vacancyName,
    eventDate,
    interviewTime,
    candidatePhone,
    candidateEmail,
    candidateTelegram,
}) {
    const name = String(candidateName || "").trim() || "кандидат";
    const vacancy = String(vacancyName || "").trim() || "вакансия не указана";
    const datePart = formatDateRu(eventDate, "дата не указана");
    const timePart = String(interviewTime || "").trim() || "время не указано";

    const contacts = [
        candidatePhone ? `тел.: ${String(candidatePhone).trim()}` : null,
        candidateEmail ? `email: ${String(candidateEmail).trim()}` : null,
        candidateTelegram ? `telegram: ${String(candidateTelegram).trim()}` : null,
    ].filter(Boolean);

    const contactsText = contacts.length
        ? ` Контакты кандидата: ${contacts.join(", ")}.`
        : "";

    return `Напоминание о собеседовании: ${name} на вакансию «${vacancy}». Дата и время собеседования: ${datePart}, ${timePart}.${contactsText}`;
}
