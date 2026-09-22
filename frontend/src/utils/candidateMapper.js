const GENDER_MAP = {
    "мужчина":"male",
    "женщина":"female"
}

const WORK_EXPERIENCE_MAP = {
    "0-1 год":"noExperience",
    "1-3 года":"between1And3",
    "3-6 лет":"between3And6",
    "6+ лет":"moreThan6",
}

/** Vacancy title from active vacancy or candidate↔vacancy relation payloads. */
export function relationVacancyName(rel) {
    if (!rel || typeof rel !== "object") return null;
    return (
        rel.vacancy?.name
        || rel.name
        || rel.vacancy_name
        || rel.last_vacancy_title
        || null
    );
}

export function formatTelegramUsername(raw) {
    if (raw == null) return null;
    let s = String(raw).trim();
    if (!s) return null;
    s = s.replace(/^https?:\/\/(t\.me|telegram\.me)\//i, "").replace(/^@+/i, "");
    s = s.split("/")[0].split("?")[0].trim();
    if (!s) return null;
    return `@${s}`;
}

export function telegramHref(raw) {
    const formatted = formatTelegramUsername(raw);
    if (!formatted) return null;
    return `https://t.me/${formatted.slice(1)}`;
}

export function formatEmail(raw) {
    if (raw == null) return null;
    const s = String(raw).trim().toLowerCase();
    if (!s || !s.includes("@") || !s.includes(".")) return null;
    return s;
}

/** Фамилия Имя Отчество. HH отдаёт last_name / first_name / middle_name. */
export function formatHhFullName(person) {
    if (person == null) return null;
    if (typeof person === "string") {
        const s = person.trim();
        return s || null;
    }
    if (typeof person !== "object") return null;
    const parts = [person.last_name, person.first_name, person.middle_name]
        .map((x) => String(x || "").trim())
        .filter(Boolean);
    if (parts.length) return parts.join(" ");
    const full = String(person.full_name || "").trim();
    return full || null;
}

export function mapCandidateToBackend(data) {
    return {
        ...data,
        gender: GENDER_MAP[data.gender] || data.gender,
        total_work_expirience: WORK_EXPERIENCE_MAP[data.total_work_expirience] || data.total_work_expirience,
        ai_score: data.ai_score ?? null,
        telegram_username: formatTelegramUsername(data.telegram_username),
        email: formatEmail(data.email),
    }
}

export function mapCandidateFromBackend(data) {
    if (!data || typeof data !== "object") return data;

    const reverseGender = Object.fromEntries(
        Object.entries(GENDER_MAP).map(([k, v]) => [v, k])
    )

    const reverseWorkExp = Object.fromEntries(
        Object.entries(WORK_EXPERIENCE_MAP).map(([k, v]) => [v, k])
    )

    return {
        ...data,
        full_name: formatHhFullName(data) || data.full_name,
        status: data.status ?? data.current_status ?? null,
        vacancy_id: data.vacancy_id ?? data.last_vacancy_id ?? null,
        vacancy_name: data.vacancy_name ?? data.last_vacancy_title ?? null,
        gender: reverseGender[data.gender] || data.gender,
        total_work_expirience: reverseWorkExp[data.total_work_expirience] || data.total_work_expirience,
        telegram_username: formatTelegramUsername(data.telegram_username),
        email: formatEmail(data.email),
    }
}
