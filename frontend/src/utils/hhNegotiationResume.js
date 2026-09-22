import { formatHhFullName } from "./candidateMapper";
import { formatDateRu } from "./dateFormat";

export function formatExperienceMonths(months) {
    if (months == null || Number.isNaN(Number(months))) return null;
    const m = Number(months);
    const years = Math.floor(m / 12);
    const rest = m % 12;
    if (years && rest) return `${years} г. ${rest} мес.`;
    if (years) return `${years} г.`;
    return `${rest} мес.`;
}

export function resumeUpdatedLabel(updatedAt) {
    if (!updatedAt) return null;
    const parsed = new Date(updatedAt);
    if (Number.isNaN(parsed.getTime())) return formatDateRu(updatedAt, null);
    const days = Math.floor((Date.now() - parsed.getTime()) / 86400000);
    if (days < 0) return formatDateRu(updatedAt, null);
    if (days <= 7) return "до 7 дней";
    if (days <= 14) return "7–14 дней";
    if (days <= 30) return "до месяца";
    return formatDateRu(updatedAt, null);
}

export function mapHhResumeToProfile(resume, { vacancyName, statusLabel } = {}) {
    const r = resume && typeof resume === "object" ? resume : {};
    const amount = r.salary_amount ?? r.salary?.amount;
    const currency = r.salary_currency || r.salary?.currency || "";
    return {
        full_name: formatHhFullName(r) || r.full_name || "Без имени",
        photo_url: r.photo_url || null,
        phone_number: r.phone_number || null,
        telegram_username: r.telegram_username || null,
        email: r.email || null,
        gender: r.gender || null,
        birth_date: r.birth_date || null,
        age: r.age ?? null,
        area: r.area || null,
        marital_status: r.marital_status || null,
        salary_expectations: amount != null ? Number(amount) : null,
        salary_label:
            amount != null
                ? `${Number(amount).toLocaleString("ru-RU")} ${currency}`.trim()
                : null,
        active_search: r.active_search,
        job_search_status: r.job_search_status || null,
        resume_updated_label: resumeUpdatedLabel(r.updated_at),
        hh_resume_link: r.alternate_url || r.url || null,
        vacancy_name: vacancyName || r.title || null,
        hard_skills: Array.isArray(r.skill_set) ? r.skill_set : [],
        education: Array.isArray(r.education) ? r.education : [],
        languages: Array.isArray(r.languages) ? r.languages : [],
        experience: Array.isArray(r.experience) ? r.experience : [],
        experience_label: formatExperienceMonths(r.experience_months),
        about: r.about || null,
        status_label: statusLabel || null,
    };
}
