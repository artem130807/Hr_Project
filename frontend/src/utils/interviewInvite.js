export const DEFAULT_INTERVIEW_CONTACT_PHONE = "8 902 001 37 28";
export const DEFAULT_INTERVIEW_CONTACT_NAME = "Кудряшова Светлана Алексеевна";
export const DEFAULT_INTERVIEW_FORMAT = "очный";
export const OFFER_LETTER_HEADING = "Приглашаем вас на работу";

const MONTHS_GENITIVE = [
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
];

export function greetingNameFromFullName(fullName) {
    const parts = String(fullName || "").trim().split(/\s+/).filter(Boolean);
    if (parts.length >= 3) return `${parts[1]} ${parts[2]}`;
    if (parts.length === 2) return parts[1];
    return parts[0] || "кандидат";
}

export function formatInterviewDateTime(dateValue, timeValue) {
    const dateRaw = String(dateValue || "").trim();
    const timeRaw = String(timeValue || "").trim().slice(0, 5);
    if (!dateRaw || !timeRaw) return "";

    const iso = dateRaw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!iso) return `${dateRaw} в ${timeRaw}`;
    const day = Number(iso[3]);
    const monthIdx = Number(iso[2]) - 1;
    const month = MONTHS_GENITIVE[monthIdx] || iso[2];
    return `${day} ${month} в ${timeRaw}`;
}

export function addHourToTime(timeValue) {
    const raw = String(timeValue || "").trim().slice(0, 5);
    const match = raw.match(/^(\d{1,2}):(\d{2})$/);
    if (!match) return "";
    const hours = Number(match[1]);
    const minutes = Number(match[2]);
    const next = (hours * 60 + minutes + 60) % (24 * 60);
    const hh = String(Math.floor(next / 60)).padStart(2, "0");
    const mm = String(next % 60).padStart(2, "0");
    return `${hh}:${mm}`;
}

export const CANDIDATE_INTERVIEW_REMINDER_QUESTION =
    "Создать напоминание о собеседовании для кандидата?";

export function padDateTimeLocal(dateValue, timeValue) {
    const dateRaw = String(dateValue || "").trim();
    const timeRaw = String(timeValue || "").trim();
    if (!dateRaw || !timeRaw) return "";
    const timePart = timeRaw.length === 5 ? `${timeRaw}:00` : timeRaw;
    return `${dateRaw}T${timePart}`.slice(0, 19);
}

export function defaultCandidateReminderAt(dateValue, timeValue) {
    const raw = padDateTimeLocal(dateValue, timeValue);
    if (!raw) return "";
    const [datePart, timePart] = raw.split("T");
    const [hours, minutes] = String(timePart || "00:00").split(":").map((n) => Number(n));
    if (!Number.isFinite(hours) || !Number.isFinite(minutes)) return raw;
    let total = hours * 60 + minutes - 60;
    if (total < 0) total = 0;
    const hh = String(Math.floor(total / 60)).padStart(2, "0");
    const mm = String(total % 60).padStart(2, "0");
    return `${datePart}T${hh}:${mm}`;
}

export function candidateReminderAtIso(localValue) {
    const raw = String(localValue || "").trim();
    if (!raw) return null;
    if (/[zZ]|[+-]\d{2}:\d{2}$/.test(raw)) return raw;
    const withSeconds = raw.length === 16 ? `${raw}:00` : raw;
    return withSeconds;
}

export function buildCandidateInterviewReminderText({
    fullName,
    dateValue,
    timeValue,
    format = DEFAULT_INTERVIEW_FORMAT,
} = {}) {
    const greeting = greetingNameFromFullName(fullName);
    const when = formatInterviewDateTime(dateValue, timeValue) || "[укажите дату и время]";
    const formatLabel = String(format || DEFAULT_INTERVIEW_FORMAT).trim() || DEFAULT_INTERVIEW_FORMAT;
    return [
        `${greeting}, здравствуйте!`,
        "",
        "Напоминаем о собеседовании в ALT.",
        `Дата и время: ${when}`,
        `Формат: ${formatLabel}`,
        "",
        "Пожалуйста, подтвердите участие ответом на это сообщение. Если планы изменились — тоже напишите нам сюда.",
    ].join("\n");
}

export function applyOfferLetterHeading(text) {
    const heading = OFFER_LETTER_HEADING;
    const body = String(text || "").trim();
    if (!body) return heading;
    const lines = body.split(/\r?\n/);
    const first = String(lines[0] || "").trim().replace(/:+$/, "");
    if (first.toLowerCase() === heading.toLowerCase()) return body;
    if (["собеседование", "приглашение на собеседование"].includes(first.toLowerCase())) {
        const rest = lines.slice(1).join("\n").trim();
        return rest ? `${heading}\n\n${rest}` : heading;
    }
    return `${heading}\n\n${body}`;
}

export function buildOfferLetterText(fullName, extra = "") {
    const name = String(fullName || "кандидат").trim() || "кандидат";
    const rest = String(extra || "").trim() || (
        `Здравствуйте, ${name}!\nМы хотим сделать вам оффер на позицию [УКАЖИТЕ ПОЗИЦИЮ].\nУсловия: [зарплата/график/дата выхода]. Пожалуйста, подтвердите.`
    );
    return applyOfferLetterHeading(rest);
}

export function buildInterviewInviteText({
    fullName,
    format = DEFAULT_INTERVIEW_FORMAT,
    dateValue,
    timeValue,
    contactPhone = DEFAULT_INTERVIEW_CONTACT_PHONE,
    contactName = DEFAULT_INTERVIEW_CONTACT_NAME,
} = {}) {
    const greeting = greetingNameFromFullName(fullName);
    const when = formatInterviewDateTime(dateValue, timeValue) || "[укажите дату и время]";
    const phone = String(contactPhone || "").trim() || DEFAULT_INTERVIEW_CONTACT_PHONE;
    const person = String(contactName || "").trim() || DEFAULT_INTERVIEW_CONTACT_NAME;
    const formatLabel = String(format || DEFAULT_INTERVIEW_FORMAT).trim() || DEFAULT_INTERVIEW_FORMAT;
    return [
        `${greeting}, здравствуйте!`,
        "Приглашаем вас на собеседование",
        `Формат: ${formatLabel}`,
        `Дата и время: ${when}`,
        "Контактное лицо:",
        phone,
        person,
    ].join("\n");
}
