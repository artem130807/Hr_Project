/** Display helpers for VacancyFilter (backend WorkFormat / WorkExpirience). */

export const WORK_FORMAT_OPTIONS = [
    { value: "remote", label: "Удалёнка" },
    { value: "office", label: "Офис" },
    { value: "hybrid", label: "Гибрид" },
    { value: "field", label: "Разъездной" },
    { value: "shift", label: "Сменный" },
];

export const ACTION_OPTIONS = [
    {
        value: "discard",
        label: "Отказ",
        hint: "Кандидатам, которые не проходят условия, уйдёт отказ на HH.",
    },
    {
        value: "consider",
        label: "Подумать",
        hint: "Кандидатам, которые проходят условия, статус на HH станет «Подумать».",
    },
];

export const EXPERIENCE_OPTIONS = [
    { value: "noExperience", label: "Нет опыта" },
    { value: "between1And3", label: "1–3 года" },
    { value: "between3And6", label: "3–6 лет" },
    { value: "moreThan6", label: "Более 6 лет" },
];

export function labelWorkFormat(value) {
    if (!value) return "—";
    return WORK_FORMAT_OPTIONS.find((o) => o.value === value)?.label || String(value);
}

export function labelExperience(value) {
    if (!value) return "—";
    return EXPERIENCE_OPTIONS.find((o) => o.value === value)?.label || String(value);
}

export function labelFilterAction(value) {
    if (!value) return "Отказ";
    return ACTION_OPTIONS.find((o) => o.value === value)?.label || String(value);
}

export function formatFilterTitle(filter) {
    if (!filter) return "Фильтр";
    if (filter.city) return `Фильтр: ${filter.city}`;
    return `Фильтр #${filter.id}`;
}

export function formatFilterSummary(filter) {
    if (!filter) return "Фильтр не задан";
    const parts = [];
    if (filter.city) parts.push(`Город: ${filter.city}`);
    if (filter.age_from != null || filter.age_to != null) {
        const from = filter.age_from ?? "…";
        const to = filter.age_to ?? "…";
        parts.push(`Возраст: ${from}–${to}`);
    }
    if (filter.experience) parts.push(`Опыт: ${labelExperience(filter.experience)}`);
    if (filter.work_format) parts.push(`Формат: ${labelWorkFormat(filter.work_format)}`);
    if (parts.length === 0) return "Пустой фильтр (поля не заданы)";
    parts.push(`Статус: ${labelFilterAction(filter.action || "discard")}`);
    return parts.join(" · ");
}

/**
 * @returns {Record<string, string>} field → error message
 */
export function validateFilterForm(form) {
    const errors = {};
    const from = form?.age_from;
    const to = form?.age_to;
    if (
        from !== "" && from != null &&
        to !== "" && to != null &&
        Number(from) > Number(to)
    ) {
        errors.age = "Возраст «от» не может быть больше «до»";
    }
    const city = String(form?.city || "").trim();
    const hasAge = (from !== "" && from != null) || (to !== "" && to != null);
    const hasExperience = Boolean(form?.experience);
    const hasFormat = Boolean(form?.work_format);
    if (!city && !hasAge && !hasExperience && !hasFormat) {
        errors.criteria = "Укажите хотя бы одно условие: город, возраст, опыт или формат работы";
    }
    return errors;
}

export function normalizeFilterPayload(form) {
    const toInt = (v) => {
        if (v === "" || v == null) return null;
        const n = Number(v);
        return Number.isFinite(n) ? n : null;
    };
    return {
        city: form.city?.trim() ? form.city.trim() : null,
        age_from: toInt(form.age_from),
        age_to: toInt(form.age_to),
        experience: form.experience || null,
        work_format: form.work_format || null,
        action: form.action === "consider" ? "consider" : "discard",
    };
}

/** Map API VacancyFilter → form state for create/edit. */
export function filterToForm(filter) {
    if (!filter) {
        return {
            city: "",
            age_from: "",
            age_to: "",
            experience: "",
            work_format: "",
            action: "discard",
        };
    }
    return {
        city: filter.city ?? "",
        age_from: filter.age_from != null ? String(filter.age_from) : "",
        age_to: filter.age_to != null ? String(filter.age_to) : "",
        experience: filter.experience ?? "",
        work_format: filter.work_format ?? "",
        action: filter.action === "consider" ? "consider" : "discard",
    };
}
