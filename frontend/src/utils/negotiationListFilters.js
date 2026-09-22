import { EXPERIENCE_OPTIONS, WORK_FORMAT_OPTIONS } from "./vacancyFilterLabels";

/** Same buckets as hh-service `map_months_to_work_experience`. */
export const EXPERIENCE_ORDER = {
    noExperience: 0,
    between1And3: 1,
    between3And6: 2,
    moreThan6: 3,
};

/** Platform VacancyFilter.work_format → HH resume work_format.id */
export const WORK_FORMAT_TO_HH = {
    remote: "REMOTE",
    office: "ON_SITE",
    hybrid: "HYBRID",
    field: "FIELD_WORK",
    shift: null,
};

export const EMPTY_NEGOTIATION_FILTERS = {
    city: "",
    age_from: "",
    age_to: "",
    experience: "",
    work_format: "",
};

export function experienceFromMonths(months) {
    if (months == null || Number.isNaN(Number(months))) return null;
    const m = Number(months);
    if (m < 12) return "noExperience";
    if (m < 36) return "between1And3";
    if (m < 72) return "between3And6";
    return "moreThan6";
}

function toInt(value) {
    if (value === "" || value == null) return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
}

function normCity(value) {
    return String(value || "").toLowerCase().replace(/\s+/g, " ").trim();
}

function resumeWorkFormatIds(resume) {
    const raw = resume?.work_formats || resume?.work_format || [];
    const ids = new Set();
    if (Array.isArray(raw)) {
        for (const item of raw) {
            if (item && typeof item === "object" && item.id) ids.add(String(item.id));
            else if (typeof item === "string" && item.trim()) ids.add(item.trim());
        }
    }
    return ids;
}

export function hasNegotiationFilters(filters) {
    if (!filters) return false;
    return Boolean(
        String(filters.city || "").trim()
        || (filters.age_from !== "" && filters.age_from != null)
        || (filters.age_to !== "" && filters.age_to != null)
        || filters.experience
        || filters.work_format
    );
}

export function negotiationFilterAgeError(filters) {
    const from = toInt(filters?.age_from);
    const to = toInt(filters?.age_to);
    if (from != null && to != null && from > to) {
        return "Возраст «от» не может быть больше «до»";
    }
    return null;
}

/**
 * Same rules as hh-service `matches_vacancy_filter`, on a *normalized* list resume.
 */
export function matchesNegotiationFilters(item, filters) {
    if (!hasNegotiationFilters(filters)) return true;
    const resume = item?.resume && typeof item.resume === "object" ? item.resume : {};

    const city = String(filters.city || "").trim();
    if (city) {
        const resumeCity = resume.area || resume.city || "";
        if (!resumeCity) return false;
        const rc = normCity(resumeCity);
        const fc = normCity(city);
        if (!rc.includes(fc) && !fc.includes(rc)) return false;
    }

    const ageFrom = toInt(filters.age_from);
    const ageTo = toInt(filters.age_to);
    if (ageFrom != null || ageTo != null) {
        const age = toInt(resume.age);
        if (age == null) return false;
        if (ageFrom != null && age < ageFrom) return false;
        if (ageTo != null && age > ageTo) return false;
    }

    if (filters.experience) {
        const bucket = experienceFromMonths(resume.experience_months);
        const c = EXPERIENCE_ORDER[bucket];
        const r = EXPERIENCE_ORDER[filters.experience];
        if (c == null || r == null) return false;
        if (c < r) return false;
    }

    if (filters.work_format) {
        const hhId = WORK_FORMAT_TO_HH[filters.work_format];
        if (hhId) {
            if (!resumeWorkFormatIds(resume).has(hhId)) return false;
        }
    }

    return true;
}

export function isUnviewedNegotiation(item) {
    if (!item) return false;
    if (item.has_updates) return true;
    if (item.viewed_by_opponent === false) return true;
    return false;
}

export function filterNegotiationItems(items, { onlyUnviewed = false, filters } = {}) {
    const list = Array.isArray(items) ? items : [];
    return list.filter((item) => {
        if (onlyUnviewed && !isUnviewedNegotiation(item)) return false;
        return matchesNegotiationFilters(item, filters);
    });
}

export function uniqueResumeCities(items) {
    const seen = new Set();
    const out = [];
    for (const item of Array.isArray(items) ? items : []) {
        const city = String(item?.resume?.area || "").trim();
        if (!city) continue;
        const key = city.toLowerCase();
        if (seen.has(key)) continue;
        seen.add(key);
        out.push(city);
    }
    return out.sort((a, b) => a.localeCompare(b, "ru"));
}

export { EXPERIENCE_OPTIONS, WORK_FORMAT_OPTIONS };
